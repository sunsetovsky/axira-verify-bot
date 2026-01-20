import discord
from discord import app_commands
from discord.ext import commands
from flask import Flask, request, redirect
import requests
import json
import os
import asyncio
from datetime import datetime
import threading

# CONFIGURAZIONE - Le variabili vengono da Railway
BOT_TOKEN = os.environ.get("BOT_TOKEN")
CLIENT_ID = os.environ.get("CLIENT_ID")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET")
RAILWAY_URL = os.environ.get("RAILWAY_URL", "https://your-app.railway.app")

REDIRECT_URI = f"{RAILWAY_URL}/callback"

VERIFIED_ROLE_ID = 1271405086047993901
ADMIN_ID = 1129411746495463467
DATA_FILE = "bot_data.json"
API_ENDPOINT = "https://discord.com/api/v10"

# Bot setup
intents = discord.Intents.default()
intents.members = True
intents.guilds = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# Flask setup
app = Flask(__name__)

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return {"verified_users": {}, "oauth_tokens": {}}

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)

data = load_data()

class VerifyButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="✓ Verify", style=discord.ButtonStyle.gray, custom_id="verify_button")
    async def verify_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild.id)
        
        if guild_id in data["verified_users"] and user_id in data["verified_users"][guild_id]:
            await interaction.response.send_message("✅ You are already verified!", ephemeral=True)
            return
        
        oauth_url = f"{RAILWAY_URL}/verify?guild_id={guild_id}"
        
        embed = discord.Embed(
            title="🔐 Verification Required",
            description=f"To verify and access **Axira**, click the link below:\n\n[**Click here to verify**]({oauth_url})\n\nAfter authorizing, you will automatically receive access!",
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
        description="Welcome to **Axira**!\n\nTo access the server and participate, verify yourself by clicking the button below.\n\n**What you'll get:**\n• Full access to all channels\n• Ability to chat and interact\n• Member benefits\n\nClick **Verify** to start!",
        color=0x000000
    )
    embed.set_footer(text="Axira Security System")
    embed.timestamp = datetime.utcnow()
    
    view = VerifyButton()
    await interaction.channel.send(embed=embed, view=view)
    await interaction.response.send_message("✅ Verification system setup!", ephemeral=True)

@tree.command(name="backup", description="Add all verified members to the server")
async def backup(interaction: discord.Interaction):
    if interaction.user.id != ADMIN_ID:
        await interaction.response.send_message("❌ You don't have permission!", ephemeral=True)
        return
    
    guild_id = str(interaction.guild.id)
    verified_users_list = data["verified_users"].get(guild_id, [])
    
    if not verified_users_list:
        await interaction.response.send_message("❌ No verified users found!", ephemeral=True)
        return
    
    total = len(verified_users_list)
    
    embed = discord.Embed(
        title="🔄 Backup in Progress",
        description=f"**Progress:** 0/{total} joined the discord server",
        color=0x3498DB
    )
    
    await interaction.response.send_message(embed=embed)
    message = await interaction.original_response()
    
    joined = 0
    failed = 0
    
    for i, user_id in enumerate(verified_users_list):
        access_token = data["oauth_tokens"].get(user_id)
        
        if access_token:
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
            except:
                failed += 1
        else:
            failed += 1
        
        await asyncio.sleep(1)
        
        if (i + 1) % 10 == 0 or (i + 1) == total:
            embed.description = f"**Progress:** {joined}/{total} joined the discord server"
            await message.edit(embed=embed)
    
    embed.color = 0x00FF00 if joined >= total * 0.5 else 0xFFA500
    embed.title = "✅ Backup Complete"
    
    if failed > 0:
        embed.description = f"**Result:** {joined}/{total} members joined!\n⚠️ {failed} failed (expired tokens or already in server)"
    else:
        embed.description = f"**Result:** {joined}/{total} members joined successfully!"
    
    await message.edit(embed=embed)

@bot.event
async def on_ready():
    bot.add_view(VerifyButton())
    await tree.sync()
    print("="*60)
    print(f'✅ Bot online: {bot.user}')
    print(f'📝 Bot ID: {bot.user.id}')
    print(f'🌐 Server URL: {RAILWAY_URL}')
    print(f'🔗 Redirect URI: {REDIRECT_URI}')
    print(f'🔧 Commands synced!')
    print("="*60)

# Web server routes
@app.route('/')
def home():
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Axira Verification System</title>
        <meta charset="utf-8">
        <style>
            body {{
                font-family: Arial, sans-serif;
                background: #000;
                color: #fff;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
                margin: 0;
            }}
            .container {{
                text-align: center;
                background: #1a1a1a;
                padding: 50px;
                border-radius: 15px;
                border: 2px solid #333;
                box-shadow: 0 0 30px rgba(0,255,0,0.3);
            }}
            h1 {{
                color: #fff;
                margin-bottom: 20px;
                font-size: 36px;
            }}
            .status {{
                color: #00ff00;
                font-weight: bold;
                font-size: 24px;
                margin: 20px 0;
            }}
            .info {{
                color: #aaa;
                font-size: 14px;
                margin-top: 30px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🛡️ Axira Verification System</h1>
            <p class="status">✅ Server Online</p>
            <div class="info">
                <p>Server URL: {RAILWAY_URL}</p>
                <p>Status: Active and Running</p>
            </div>
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
        # Exchange code for access token
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
        
        # Get user info
        headers = {'Authorization': f'Bearer {access_token}'}
        r = requests.get(f'{API_ENDPOINT}/users/@me', headers=headers)
        r.raise_for_status()
        user_data = r.json()
        user_id = user_data['id']
        username = user_data['username']
        
        # Add user to guild
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
        
        # Save user data
        if guild_id not in data["verified_users"]:
            data["verified_users"][guild_id] = []
        if user_id not in data["verified_users"][guild_id]:
            data["verified_users"][guild_id].append(user_id)
        data["oauth_tokens"][user_id] = access_token
        save_data(data)
        
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Verification Complete</title>
            <meta charset="utf-8">
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                    display: flex;
                    justify-content: center;
                    align-items: center;
                    height: 100vh;
                    margin: 0;
                }}
                .container {{
                    background: white;
                    padding: 50px;
                    border-radius: 20px;
                    box-shadow: 0 15px 50px rgba(0,0,0,0.4);
                    text-align: center;
                    max-width: 450px;
                }}
                h1 {{
                    color: #667eea;
                    margin-bottom: 20px;
                    font-size: 32px;
                }}
                p {{
                    color: #666;
                    font-size: 18px;
                    line-height: 1.8;
                }}
                .checkmark {{
                    font-size: 100px;
                    color: #00d084;
                    margin-bottom: 20px;
                    animation: scale 0.5s ease-in-out;
                }}
                .username {{
                    font-weight: bold;
                    color: #667eea;
                }}
                @keyframes scale {{
                    0% {{ transform: scale(0); }}
                    50% {{ transform: scale(1.1); }}
                    100% {{ transform: scale(1); }}
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="checkmark">✓</div>
                <h1>Verification Complete!</h1>
                <p>Welcome to <strong>Axira</strong>, <span class="username">{username}</span>!</p>
                <p>You now have full access to the server.</p>
                <p style="color: #999; font-size: 14px; margin-top: 30px;">You can safely close this window.</p>
            </div>
        </body>
        </html>
        """
    except Exception as e:
        return f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Error</title>
            <meta charset="utf-8">
        </head>
        <body style="font-family: Arial; text-align: center; padding: 50px; background: #f5f5f5;">
            <h1 style="color: #e74c3c;">❌ Verification Failed</h1>
            <p style="color: #666;">An error occurred during verification.</p>
            <p style="color: #999; font-size: 14px;">Error: {str(e)}</p>
            <p>Please try again or contact an administrator.</p>
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
    print("🚀 Starting Axira Verification Bot on Railway")
    print(f"🌐 Server URL: {RAILWAY_URL}")
    
    # Start Flask in background thread
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Start Discord bot
    bot.run(BOT_TOKEN)