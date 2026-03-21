# bot.py
import discord
from discord.ext import commands
import requests
import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
API_URL = os.getenv('YOUR_DOMAIN', 'http://127.0.0.1:4242')

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'✅ Bot: {bot.user}')

@bot.command()
async def balance(ctx):
    try:
        r = requests.get(f'{API_URL}/api/bot/check_balance/{ctx.author.id}')
        if r.status_code == 200:
            data = r.json()
            await ctx.send(f"💰 {data['username']}: ${data['balance']:.2f}")
        else:
            await ctx.send("❌ Nincs fiókod!")
    except:
        await ctx.send("❌ Hiba")

@bot.command()
async def products(ctx):
    try:
        r = requests.get(f'{API_URL}/api/products')
        if r.status_code == 200:
            products = r.json()
            msg = "**Termékek:**\n"
            for p in products[:5]:
                msg += f"{p['name']} - ${p['price']}\n"
            await ctx.send(msg)
    except:
        await ctx.send("❌ Hiba")

bot.run(BOT_TOKEN)