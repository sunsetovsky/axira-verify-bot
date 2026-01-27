import discord
from discord import app_commands
from discord.ext import commands
from flask import Flask, request, redirect
import requests
import os
import asyncio
from datetime import datetime
import threading
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure

# CONFIGURAZIONE
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CLIENT_ID = os.environ.get("CLIENT_ID")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET")
RAILWAY_URL = os.environ.get("RAILWAY_URL", "https://your-app.railway.app")
MONGODB_URI = os.environ.get("MONGODB_URI")

REDIRECT_URI = f"{RAILWAY_URL}/callback"

VERIFIED_ROLE_ID = 1271405086047993901
ADMIN_ID = 1129411746495463467
API_ENDPOINT = "https://discord.com/api/v10"

# MongoDB setup
try:
    mongo_client = MongoClient(MONGODB_URI)
    db = mongo_client.axira_bot
    verified_collection = db.verified_users
    tokens_collection = db.oauth_tokens
    print("✅ MongoDB connected successfully!")
except ConnectionFailure as e:
    print(f"❌ MongoDB connection failed: {e}")
    mongo_client = None

# Bot setup
intents = discord.Intents.default()
intents.members = True
intents.guilds = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# Flask setup
app = Flask(__name__)

def save_verified_user(guild_id: str, user_id: str):
    """Salva utente verificato nel database"""
    try:
        verified_collection.update_one(
            {"guild_id": guild_id, "user_id": user_id},
            {"$set": {"guild_id": guild_id, "user_id": user_id, "verified_at": datetime.utcnow()}},
            upsert=True
        )
        return True
    except Exception as e:
        print(f"[ERROR] Failed to save verified user: {e}")
        return False

def save_oauth_token(user_id: str, access_token: str):
    """Salva token OAuth2 nel database"""
    try:
        tokens_collection.update_one(
            {"user_id": user_id},
            {"$set": {"user_id": user_id, "access_token": access_token, "updated_at": datetime.utcnow()}},
            upsert=True
        )
        return True
    except Exception as e:
        print(f"[ERROR] Failed to save token: {e}")
        return False

def get_verified_users(guild_id: str):
    """Ottieni tutti gli utenti verificati di un server"""
    try:
        users = list(verified_collection.find({"guild_id": guild_id}))
        return [user["user_id"] for user in users]
    except Exception as e:
        print(f"[ERROR] Failed to get verified users: {e}")
        return []

def get_oauth_token(user_id: str):
    """Ottieni token OAuth2 di un utente"""
    try:
        token_doc = tokens_collection.find_one({"user_id": user_id})
        return token_doc["access_token"] if token_doc else None
    except Exception as e:
        print(f"[ERROR] Failed to get token: {e}")
        return None

def is_user_verified(guild_id: str, user_id: str):
    """Controlla se un utente è verificato"""
    try:
        return verified_collection.find_one({"guild_id": guild_id, "user_id": user_id}) is not None
    except Exception as e:
        print(f"[ERROR] Failed to check verification: {e}")
        return False

def is_user_in_guild(guild_id: str, user_id: str) -> bool:
    """Controlla se un utente è nel server"""
    try:
        headers = {'Authorization': f'Bot {BOT_TOKEN}'}
        r = requests.get(
            f'{API_ENDPOINT}/guilds/{guild_id}/members/{user_id}',
            headers=headers,
            timeout=5
        )
        return r.status_code == 200
    except:
        return False

class VerifyButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="✓ Verify", style=discord.ButtonStyle.gray, custom_id="verify_btn_persistent")
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild.id)
        
        # Controlla se già verificato
        if is_user_verified(guild_id, user_id):
            await interaction.response.send_message("✅ You are already verified!", ephemeral=True)
            return
        
        oauth_url = f"{RAILWAY_URL}/verify?guild_id={guild_id}"
        
        embed = discord.Embed(
            title="🔐 Verification Required",
            description=f"To verify and access **Axira**, click the link below:\n\n[**Click here to verify**]({oauth_url})\n\nAfter authorizing, you will receive the **Verified** role!",
            color=0x000000
        )
        embed.set_footer(text="Axira Verification System")
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

@tree.command(name="setupverify", description="Setup the verification system")
async def setupverify(interaction: discord.Interaction):
    if interaction.user.id != ADMIN_ID:
        await interaction.response.send_message("❌ You don't have permission!", ephemeral=True)
        return
    
    embed = discord.Embed(
        title="🛡️ Axira Verification",
        description="Welcome to **Axira**!\n\nTo access the server and participate, verify yourself by clicking the button below.\n\n**What you'll get:**\n• Full access to all channels\n• Ability to chat and interact\n• Member benefits and updates\n\nClick **Verify** to start!",
        color=0x000000
    )
    embed.set_footer(text="Axira Security System")
    embed.timestamp = datetime.utcnow()
    
    view = VerifyButton()
    await interaction.channel.send(embed=embed, view=view)
    await interaction.response.send_message("✅ Verification system setup complete!", ephemeral=True)

@tree.command(name="verified", description="Show verified members statistics")
async def verified(interaction: discord.Interaction):
    if interaction.user.id != ADMIN_ID:
        await interaction.response.send_message("❌ You don't have permission!", ephemeral=True)
        return
    
    guild_id = str(interaction.guild.id)
    verified_users_list = get_verified_users(guild_id)
    
    if not verified_users_list:
        await interaction.response.send_message("❌ No verified users found!", ephemeral=True)
        return
    
    total = len(verified_users_list)
    
    embed = discord.Embed(
        title="📊 Checking Verified Members...",
        description="Please wait, checking server members...",
        color=0x3498DB
    )
    await interaction.response.send_message(embed=embed)
    message = await interaction.original_response()
    
    in_server = 0
    left_server = 0
    
    for user_id in verified_users_list:
        if is_user_in_guild(guild_id, user_id):
            in_server += 1
        else:
            left_server += 1
        await asyncio.sleep(0.3)
    
    embed = discord.Embed(
        title="📊 Verified Members Statistics",
        description="Complete statistics of verified members",
        color=0x00FF00
    )
    
    embed.add_field(
        name="📝 Total Verified",
        value=f"**{total}** members",
        inline=True
    )
    
    embed.add_field(
        name="✅ In Server",
        value=f"**{in_server}** members",
        inline=True
    )
    
    embed.add_field(
        name="❌ Left Server",
        value=f"**{left_server}** members",
        inline=True
    )
    
    percentage = (in_server / total * 100) if total > 0 else 0
    
    embed.add_field(
        name="📈 Retention Rate",
        value=f"**{percentage:.1f}%**",
        inline=False
    )
    
    embed.set_footer(text=f"Axira • {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC")
    
    await message.edit(embed=embed)

@tree.command(name="backup", description="Add all verified members to the server")
async def backup(interaction: discord.Interaction):
    if interaction.user.id != ADMIN_ID:
        await interaction.response.send_message("❌ You don't have permission!", ephemeral=True)
        return
    
    guild_id = str(interaction.guild.id)
    verified_users_list = get_verified_users(guild_id)
    
    if not verified_users_list:
        await interaction.response.send_message("❌ No verified users found!", ephemeral=True)
        return
    
    total = len(verified_users_list)
    
    embed = discord.Embed(
        title="🔄 Backup in Progress",
        description=f"**Progress:** 0/{total} processed\n\n**✅ Joined:** 0\n**📍 Already in server:** 0\n**❌ Failed:** 0",
        color=0x3498DB
    )
    
    await interaction.response.send_message(embed=embed)
    message = await interaction.original_response()
    
    joined = 0
    already_in = 0
    failed = 0
    
    for i, user_id in enumerate(verified_users_list):
        access_token = get_oauth_token(user_id)
        
        is_in_server = is_user_in_guild(guild_id, user_id)
        
        if is_in_server:
            already_in += 1
            
            headers = {
                'Authorization': f'Bot {BOT_TOKEN}',
                'Content-Type': 'application/json'
            }
            
            try:
                r = requests.patch(
                    f'{API_ENDPOINT}/guilds/{guild_id}/members/{user_id}',
                    headers=headers,
                    json={'roles': [str(VERIFIED_ROLE_ID)]},
                    timeout=10
                )
                
                if r.status_code not in [200, 204]:
                    print(f"[WARN] Could not add role to user {user_id}: {r.status_code}")
            except Exception as e:
                print(f"[ERROR] Role assignment failed for {user_id}: {e}")
        
        elif access_token:
            headers = {
                'Authorization': f'Bot {BOT_TOKEN}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'access_token': access_token,
                'roles': [str(VERIFIED_ROLE_ID)]
            }
            
            try:
                r = requests.put(
                    f'{API_ENDPOINT}/guilds/{guild_id}/members/{user_id}',
                    headers=headers,
                    json=payload,
                    timeout=10
                )
                
                if r.status_code in [201, 204]:
                    joined += 1
                else:
                    failed += 1
                    print(f"[WARN] Failed to add user {user_id}: {r.status_code}")
            except Exception as e:
                failed += 1
                print(f"[ERROR] Failed to add user {user_id}: {e}")
        else:
            failed += 1
        
        await asyncio.sleep(1)
        
        if (i + 1) % 5 == 0 or (i + 1) == total:
            progress = i + 1
            embed.description = (
                f"**Progress:** {progress}/{total} processed\n\n"
                f"**✅ Joined:** {joined}\n"
                f"**📍 Already in server:** {already_in}\n"
                f"**❌ Failed:** {failed}"
            )
            await message.edit(embed=embed)
    
    embed.color = 0x00FF00
    embed.title = "✅ Backup Complete"
    
    summary_lines = [
        f"**Total processed:** {total} members",
        f"**✅ Successfully joined:** {joined} members",
        f"**📍 Already in server:** {already_in} members"
    ]
    
    if failed > 0:
        summary_lines.append(f"**❌ Failed:** {failed} members (expired tokens or errors)")
    
    embed.description = "\n".join(summary_lines)
    embed.set_footer(text="Backup completed successfully")
    
    await message.edit(embed=embed)

view_added = False

@bot.event
async def on_ready():
    global view_added
    
    if not view_added:
        bot.add_view(VerifyButton())
        view_added = True
    
    await tree.sync()
    
    # Conta utenti verificati
    total_verified = verified_collection.count_documents({})
    
    print("="*60)
    print(f'✅ Bot online: {bot.user}')
    print(f'📝 Bot ID: {bot.user.id}')
    print(f'🌐 Server URL: {RAILWAY_URL}')
    print(f'🔗 Redirect URI: {REDIRECT_URI}')
    print(f'🔧 Commands synced!')
    print(f'💾 Total verified users in database: {total_verified}')
    print("="*60)

# Web server routes
@app.route('/')
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Axira Verification System</title>
        <meta charset="utf-8">
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            
            body {
                font-family: 'Arial', sans-serif;
                background: #000;
                color: #fff;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                overflow: hidden;
                position: relative;
            }
            
            .snowflake {
                position: absolute;
                top: -10px;
                color: #fff;
                font-size: 1.5em;
                opacity: 0.9;
                animation: fall linear infinite;
                z-index: 1;
            }
            
            @keyframes fall {
                to {
                    transform: translateY(100vh);
                }
            }
            
            .neon-bar {
                position: absolute;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                background: rgba(255, 255, 255, 0.1);
                backdrop-filter: blur(10px);
                border: 3px solid #fff;
                border-radius: 20px;
                padding: 60px 80px;
                box-shadow: 
                    0 0 20px rgba(255, 255, 255, 0.5),
                    0 0 40px rgba(255, 255, 255, 0.3),
                    inset 0 0 20px rgba(255, 255, 255, 0.1);
                text-align: center;
                z-index: 10;
                animation: pulse-glow 2s ease-in-out infinite;
            }
            
            @keyframes pulse-glow {
                0%, 100% {
                    box-shadow: 
                        0 0 20px rgba(255, 255, 255, 0.5),
                        0 0 40px rgba(255, 255, 255, 0.3),
                        inset 0 0 20px rgba(255, 255, 255, 0.1);
                }
                50% {
                    box-shadow: 
                        0 0 30px rgba(255, 255, 255, 0.7),
                        0 0 60px rgba(255, 255, 255, 0.5),
                        inset 0 0 30px rgba(255, 255, 255, 0.2);
                }
            }
            
            .star-pfp {
                width: 120px;
                height: 120px;
                margin: 0 auto 30px;
                filter: drop-shadow(0 0 20px rgba(255, 255, 255, 0.8));
                animation: float 3s ease-in-out infinite;
            }
            
            @keyframes float {
                0%, 100% {
                    transform: translateY(0px);
                }
                50% {
                    transform: translateY(-15px);
                }
            }
            
            h1 {
                color: #fff;
                font-size: 32px;
                text-transform: uppercase;
                letter-spacing: 4px;
                margin-bottom: 20px;
                text-shadow: 
                    0 0 10px rgba(255, 255, 255, 0.8),
                    0 0 20px rgba(255, 255, 255, 0.6),
                    0 0 30px rgba(255, 255, 255, 0.4);
            }
            
            .status {
                color: #00ff00;
                font-size: 18px;
                font-weight: bold;
                text-shadow: 0 0 10px rgba(0, 255, 0, 0.8);
            }
            
            .floating-star {
                position: absolute;
                font-size: 40px;
                opacity: 0.8;
                animation: float-across 15s linear infinite;
                z-index: 5;
            }
            
            @keyframes float-across {
                0% {
                    left: -100px;
                    transform: rotate(0deg);
                }
                100% {
                    left: calc(100% + 100px);
                    transform: rotate(360deg);
                }
            }
        </style>
    </head>
    <body>
        <div class="snowflake" style="left: 10%; animation-duration: 10s; animation-delay: 0s;">❄</div>
        <div class="snowflake" style="left: 20%; animation-duration: 8s; animation-delay: 1s;">❄</div>
        <div class="snowflake" style="left: 30%; animation-duration: 12s; animation-delay: 0.5s;">❄</div>
        <div class="snowflake" style="left: 40%; animation-duration: 9s; animation-delay: 2s;">❄</div>
        <div class="snowflake" style="left: 50%; animation-duration: 11s; animation-delay: 1.5s;">❄</div>
        <div class="snowflake" style="left: 60%; animation-duration: 10s; animation-delay: 0.8s;">❄</div>
        <div class="snowflake" style="left: 70%; animation-duration: 13s; animation-delay: 1.2s;">❄</div>
        <div class="snowflake" style="left: 80%; animation-duration: 8s; animation-delay: 0.3s;">❄</div>
        <div class="snowflake" style="left: 90%; animation-duration: 9s; animation-delay: 1.8s;">❄</div>
        
        <div class="floating-star" style="top: 20%; animation-delay: 0s;">⭐</div>
        <div class="floating-star" style="top: 50%; animation-delay: 5s;">⭐</div>
        <div class="floating-star" style="top: 70%; animation-delay: 10s;">⭐</div>
        
        <div class="neon-bar">
            <svg class="star-pfp" viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
                <path d="M100,20 L115,70 L165,70 L125,100 L140,150 L100,120 L60,150 L75,100 L35,70 L85,70 Z" 
                      fill="white" stroke="black" stroke-width="2"/>
                <ellipse cx="75" cy="85" rx="8" ry="15" fill="black"/>
                <ellipse cx="125" cy="85" rx="8" ry="15" fill="black"/>
                <path d="M 70,120 Q 100,110 130,120" stroke="black" stroke-width="4" fill="none" stroke-linecap="round"/>
            </svg>
            
            <h1>AXIRA VERIFICATION SYSTEM</h1>
            <p class="status">✅ ONLINE</p>
        </div>
    </body>
    </html>
    """

@app.route('/verify')
def verify():
    guild_id = request.args.get('guild_id')
    
    oauth_url = (
        f"https://discord.com/oauth2/authorize"
        f"?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
        f"&scope=identify%20guilds.join"
        f"&state={guild_id}"
    )
    
    return redirect(oauth_url)

@app.route('/callback')
def callback():
    code = request.args.get('code')
    guild_id = request.args.get('state')
    
    if not code:
        return "❌ Authorization failed!", 400
    
    try:
        token_data = {
            'client_id': CLIENT_ID,
            'client_secret': CLIENT_SECRET,
            'grant_type': 'authorization_code',
            'code': code,
            'redirect_uri': REDIRECT_URI
        }
        
        headers = {'Content-Type': 'application/x-www-form-urlencoded'}
        r = requests.post(f'{API_ENDPOINT}/oauth2/token', data=token_data, headers=headers)
        r.raise_for_status()
        token_response = r.json()
        access_token = token_response['access_token']
        
        headers = {'Authorization': f'Bearer {access_token}'}
        r = requests.get(f'{API_ENDPOINT}/users/@me', headers=headers)
        r.raise_for_status()
        user_data = r.json()
        user_id = user_data['id']
        username = user_data['username']
        
        print(f"[INFO] User {username} ({user_id}) verifying for guild {guild_id}")
        
        headers = {
            'Authorization': f'Bot {BOT_TOKEN}',
            'Content-Type': 'application/json'
        }
        payload = {
            'access_token': access_token,
            'roles': [str(VERIFIED_ROLE_ID)]
        }
        
        r = requests.put(
            f'{API_ENDPOINT}/guilds/{guild_id}/members/{user_id}',
            headers=headers,
            json=payload
        )
        
        print(f"[INFO] PUT /members: {r.status_code}")
        
        if r.status_code == 204 or r.status_code >= 400:
            print(f"[INFO] User in server, adding role...")
            r = requests.patch(
                f'{API_ENDPOINT}/guilds/{guild_id}/members/{user_id}',
                headers=headers,
                json={'roles': [str(VERIFIED_ROLE_ID)]}
            )
            print(f"[INFO] PATCH /members: {r.status_code}")
        
        # Salva nel database MongoDB
        save_verified_user(guild_id, user_id)
        save_oauth_token(user_id, access_token)
        
        print(f"[SUCCESS] User {username} verified and saved to MongoDB!")
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Verification Complete</title>
            <meta charset="utf-8">
            <style>
                * {{
                    margin: 0;
                    padding: 0;
                    box-sizing: border-box;
                }}
                
                body {{
                    font-family: Arial, sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    overflow: hidden;
                    position: relative;
                }}
                
                .particles {{
                    position: fixed;
                    top: 0;
                    left: 0;
                    width: 100%;
                    height: 100%;
                    pointer-events: none;
                }}
                
                .particle {{
                    position: absolute;
                    background: rgba(255, 255, 255, 0.6);
                    border-radius: 50%;
                    animation: float-up linear infinite;
                }}
                
                @keyframes float-up {{
                    0% {{
                        transform: translateY(100vh) scale(0);
                        opacity: 0;
                    }}
                    10% {{
                        opacity: 1;
                    }}
                    90% {{
                        opacity: 1;
                    }}
                    100% {{
                        transform: translateY(-100px) scale(1);
                        opacity: 0;
                    }}
                }}
                
                .container {{
                    background: white;
                    padding: 60px 50px;
                    border-radius: 25px;
                    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
                    text-align: center;
                    max-width: 500px;
                    animation: slideIn 0.5s ease-out;
                    position: relative;
                    z-index: 10;
                }}
                
                @keyframes slideIn {{
                    from {{
                        opacity: 0;
                        transform: scale(0.8);
                    }}
                    to {{
                        opacity: 1;
                        transform: scale(1);
                    }}
                }}
                
                .checkmark {{
                    font-size: 120px;
                    margin-bottom: 25px;
                    animation: checkPop 0.6s cubic-bezier(0.68, -0.55, 0.265, 1.55);
                }}
                
                @keyframes checkPop {{
                    0% {{
                        transform: scale(0) rotate(-180deg);
                        opacity: 0;
                    }}
                    100% {{
                        transform: scale(1) rotate(0deg);
                        opacity: 1;
                    }}
                }}
                
                h1 {{
                    color: #667eea;
                    margin-bottom: 25px;
                    font-size: 36px;
                }}
                
                .username {{
                    font-weight: bold;
                    color: #667eea;
                    font-size: 22px;
                }}
                
                .role-badge {{
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    color: white;
                    padding: 15px 30px;
                    border-radius: 10px;
                    margin: 25px 0;
                    font-weight: bold;
                    font-size: 18px;
                    display: inline-block;
                    box-shadow: 0 5px 15px rgba(102, 126, 234, 0.4);
                }}
            </style>
        </head>
        <body>
            <div class="particles">
                <div class="particle" style="left: 10%; width: 4px; height: 4px; animation-duration: 8s; animation-delay: 0s;"></div>
                <div class="particle" style="left: 20%; width: 6px; height: 6px; animation-duration: 10s; animation-delay: 1s;"></div>
                <div class="particle" style="left: 30%; width: 5px; height: 5px; animation-duration: 12s; animation-delay: 0.5s;"></div>
                <div class="particle" style="left: 40%; width: 7px; height: 7px; animation-duration: 9s; animation-delay: 2s;"></div>
                <div class="particle" style="left: 50%; width: 4px; height: 4px; animation-duration: 11s; animation-delay: 1.5s;"></div>
                <div class="particle" style="left: 60%; width: 6px; height: 6px; animation-duration: 10s; animation-delay: 0.8s;"></div>
                <div class="particle" style="left: 70%; width: 5px; height: 5px; animation-duration: 13s; animation-delay: 1.2s;"></div>
                <div class="particle" style="left: 80%; width: 7px; height: 7px; animation-duration: 8s; animation-delay: 0.3s;"></div>
                <div class="particle" style="left: 90%; width: 4px; height: 4px; animation-duration: 9s; animation-delay: 1.8s;"></div>
            </div>
            
            <div class="container">
                <div class="checkmark">✅</div>
                <h1>Verification Complete!</h1>
                <p style="font-size: 20px; color: #666; margin-bottom: 20px;">
                    Welcome to <strong>Axira</strong>, <span class="username">{username}</span>!
                </p>
                
                <div class="role-badge">
                    🎉 Verified Role Assigned!
                </div>
                
                <p style="color: #999; margin-top: 30px;">You can close this window now.</p>
            </div>
        </body>
        </html>
        """
    except Exception as e:
        print(f"[ERROR] Verification failed: {str(e)}")
        return f"""
        <html>
        <head><title>Error</title></head>
        <body style="font-family: Arial; text-align: center; padding: 50px; background: #f5f5f5;">
            <div style="background: white; padding: 40px; border-radius: 15px; max-width: 500px; margin: 0 auto;">
                <h1 style="color: #e74c3c;">❌ Verification Failed</h1>
                <p style="color: #666;">An error occurred. Please try again.</p>
                <p style="color: #999; font-size: 12px; margin-top: 20px;">Error: {str(e)}</p>
            </div>
        </body>
        </html>
        """, 500

@app.route('/health')
def health():
    return "OK", 200

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

if __name__ == '__main__':
    print("🚀 Starting Axira Verification Bot with MongoDB")
    print(f"🌐 Server URL: {RAILWAY_URL}")
    
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    bot.run(BOT_TOKEN)
