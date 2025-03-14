import discord
from discord.ext import commands
import yt_dlp as youtube_dl  # Cambiado a yt-dlp
import asyncio
import spotipy
import re
from spotipy.oauth2 import SpotifyClientCredentials
from dotenv import load_dotenv
import os

load_dotenv()

# Obtener credenciales desde las variables de entorno
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# Configura credenciales de Spotify
sp = spotipy.Spotify(
    auth_manager=SpotifyClientCredentials(
        client_id=SPOTIFY_CLIENT_ID,
        client_secret=SPOTIFY_CLIENT_SECRET
    )
)

# Configura el bot
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Opciones para yt-dlp
ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': True,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'
}
ffmpeg_options = {'options': '-vn'}
ytdl = youtube_dl.YoutubeDL(ytdl_format_options)


class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=True):  # Cambia stream a True por defecto
        loop = loop or asyncio.get_event_loop()
        try:
            data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))
        except Exception as e:
            print(f"Error al extraer información: {e}")
            return None

        if 'entries' in data:
            data = data['entries'][0]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)


# Comando para unirse al canal de voz
@bot.command()
async def join(ctx):
    if ctx.author.voice:
        channel = ctx.author.voice.channel  
        await channel.connect()
    else:
        await ctx.send("¡Debes estar en un canal de voz para usar este comando!")


# Comando para reproducir música
@bot.command()
async def play(ctx, *, url):
    if "open.spotify.com/track" in url:
        match = re.search(r'track/([^?]+)', url)
        if not match:
            await ctx.send("URL de Spotify inválida.")
            return
        track_id = match.group(1)
        try:
            track_info = sp.track(track_id)
            song_name = track_info["name"]
            artist = track_info["artists"][0]["name"]
            search_query = f"{song_name} {artist} audio"
            url = f"ytsearch:{search_query}"
        except Exception as e:
            await ctx.send("No se pudo obtener información de Spotify.")
            print(f"Error en Spotify API: {e}")
            return

    async with ctx.typing():
        player = await YTDLSource.from_url(url, loop=bot.loop, stream=True)
        if not player:
            await ctx.send("No se encontró la canción en YouTube.")
            return
        ctx.voice_client.play(player, after=lambda e: print(f"Error: {e}") if e else None)
        await ctx.send(f"Reproduciendo: **{player.title}**")
# Comando para desconectarse del canal de voz
@bot.command()
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("¡Me he desconectado del canal de voz!")
    else:
        await ctx.send("No estoy conectado a ningún canal de voz.")


# Comando para detener la música
@bot.command()
async def stop(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()
        await ctx.send("Reproducción detenida.")
    else:
        await ctx.send("No hay música reproduciéndose.")

# Inicia el bot
bot.run(DISCORD_TOKEN)
