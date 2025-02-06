import discord
from discord.ext import commands, tasks
from discord.ui import Button, View, Select
import random
import asyncio
import sqlite3
from datetime import datetime, timedelta

# Configurações iniciais
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Banco de dados
conn = sqlite3.connect('economy.db')
c = conn.cursor()

# Tabela de usuários
c.execute('''CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER DEFAULT 1000
            )''')

# Tabela de transações
c.execute('''CREATE TABLE IF NOT EXISTS transactions (
                transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                type TEXT,
                amount INTEGER,
                timestamp TEXT
            )''')

# Tabela de eventos
c.execute('''CREATE TABLE IF NOT EXISTS events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                reward INTEGER,
                end_time TEXT
            )''')

# Tabela de inventário
c.execute('''CREATE TABLE IF NOT EXISTS inventory (
                user_id INTEGER,
                item_name TEXT,
                quantity INTEGER,
                PRIMARY KEY (user_id, item_name)
            )''')
conn.commit()

# GIFs
COIN_FLIP_GIF = "https://media.giphy.com/media/3o7aD2d7hy9ktXNDP2/giphy.gif"
DICE_ROLL_GIF = "https://media.giphy.com/media/3o7abKhOpu0NwenH3O/giphy.gif"
ROULETTE_GIF = "https://media.giphy.com/media/3o7aD2d7hy9ktXNDP2/giphy.gif"

# Variável de evento ativo
active_event = None

# Função para criar embeds
def create_embed(title, description, color=discord.Color.blue()):
    embed = discord.Embed(title=title, description=description, color=color)
    return embed

# Função para registrar transações
def log_transaction(user_id, transaction_type, amount):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    c.execute('INSERT INTO transactions (user_id, type, amount, timestamp) VALUES (?, ?, ?, ?)',
              (user_id, transaction_type, amount, timestamp))
    conn.commit()

# Verificar e atualizar eventos
@tasks.loop(minutes=1)
async def check_events():
    global active_event
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    c.execute('SELECT * FROM events WHERE end_time <= ?', (now,))
    expired_events = c.fetchall()
    for event in expired_events:
        c.execute('DELETE FROM events WHERE event_id = ?', (event[0],))
        conn.commit()
    if active_event and active_event[3] <= now:
        active_event = None

# Comando para iniciar o bot
@bot.event
async def on_ready():
    print(f'Bot {bot.user.name} está online!')
    check_events.start()

# Painel de Controle
class ControlPanel(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Saldo", style=discord.ButtonStyle.primary, emoji="💰")
    async def balance_button(self, interaction: discord.Interaction, button: Button):
        user_id = interaction.user.id
        c.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
        result = c.fetchone()
        if result:
            embed = create_embed(
                title="💰 Saldo",
                description=f"{interaction.user.mention}, seu saldo é de **{result[0]} moedas**.",
                color=discord.Color.gold()
            )
        else:
            embed = create_embed(
                title="❌ Erro",
                description=f"{interaction.user.mention}, você precisa se registrar primeiro. Use `!registrar`.",
                color=discord.Color.red()
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Apostar", style=discord.ButtonStyle.green, emoji="🎲")
    async def bet_button(self, interaction: discord.Interaction, button: Button):
        embed = create_embed(
            title="🎲 Escolha o Jogo",
            description="Escolha um jogo para apostar:",
            color=discord.Color.blue()
        )
        view = BetOptions()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# Opções de Aposta
class BetOptions(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Cara ou Coroa", style=discord.ButtonStyle.primary, emoji="🪙")
    async def coin_flip_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(CoinFlipModal())

    @discord.ui.button(label="Dados", style=discord.ButtonStyle.primary, emoji="🎲")
    async def dice_roll_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(DiceRollModal())

    @discord.ui.button(label="Roleta", style=discord.ButtonStyle.primary, emoji="🎡")
    async def roulette_button(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(RouletteModal())

# Modal para Cara ou Coroa
class CoinFlipModal(discord.ui.Modal, title="Apostar em Cara ou Coroa"):
    amount = discord.ui.TextInput(label="Quantidade de Moedas", placeholder="Digite a quantidade...")
    choice = discord.ui.TextInput(label="Escolha (cara/coroa)", placeholder="Digite 'cara' ou 'coroa'...")

    async def on_submit(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        c.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
        result = c.fetchone()
        if not result:
            await interaction.response.send_message(embed=create_embed(
                title="❌ Erro",
                description=f"{interaction.user.mention}, você precisa se registrar primeiro. Use `!registrar`.",
                color=discord.Color.red()
            ), ephemeral=True)
            return

        balance = result[0]
        try:
            amount = int(self.amount.value)
            choice = self.choice.value.lower()
        except ValueError:
            await interaction.response.send_message(embed=create_embed(
                title="❌ Erro",
                description=f"{interaction.user.mention}, valor inválido.",
                color=discord.Color.red()
            ), ephemeral=True)
            return

        if amount <= 0 or amount > balance:
            await interaction.response.send_message(embed=create_embed(
                title="❌ Erro",
                description=f"{interaction.user.mention}, valor inválido ou saldo insuficiente.",
                color=discord.Color.red()
            ), ephemeral=True)
            return

        if choice not in ["cara", "coroa"]:
            await interaction.response.send_message(embed=create_embed(
                title="❌ Erro",
                description=f"{interaction.user.mention}, escolha 'cara' ou 'coroa'.",
                color=discord.Color.red()
            ), ephemeral=True)
            return

        embed = create_embed(
            title="🪙 Lançando a Moeda...",
            description=f"{interaction.user.mention} está apostando **{amount} moedas** em **{choice}**!",
            color=discord.Color.blue()
        )
        embed.set_image(url=COIN_FLIP_GIF)
        message = await interaction.response.send_message(embed=embed)

        await asyncio.sleep(3)

        result = random.choice(["cara", "coroa"])
        if choice == result:
            new_balance = balance + amount
            embed = create_embed(
                title="🎉 Você Ganhou!",
                description=f"Resultado: **{result}**!\n{interaction.user.mention}, você ganhou **{amount} moedas**! Seu novo saldo é **{new_balance}**.",
                color=discord.Color.green()
            )
        else:
            new_balance = balance - amount
            embed = create_embed(
                title="😢 Você Perdeu!",
                description=f"Resultado: **{result}**!\n{interaction.user.mention}, você perdeu **{amount} moedas**. Seu novo saldo é **{new_balance}**.",
                color=discord.Color.red()
            )

        c.execute('UPDATE users SET balance = ? WHERE user_id = ?', (new_balance, user_id))
        log_transaction(user_id, "coin_flip", amount if choice == result else -amount)
        conn.commit()
        await interaction.edit_original_response(embed=embed)

# Modal para Dados
class DiceRollModal(discord.ui.Modal, title="Apostar em Dados"):
    amount = discord.ui.TextInput(label="Quantidade de Moedas", placeholder="Digite a quantidade...")
    choice = discord.ui.TextInput(label="Escolha (1-6)", placeholder="Digite um número de 1 a 6...")

    async def on_submit(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        c.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
        result = c.fetchone()
        if not result:
            await interaction.response.send_message(embed=create_embed(
                title="❌ Erro",
                description=f"{interaction.user.mention}, você precisa se registrar primeiro. Use `!registrar`.",
                color=discord.Color.red()
            ), ephemeral=True)
            return

        balance = result[0]
        try:
            amount = int(self.amount.value)
            choice = int(self.choice.value)
        except ValueError:
            await interaction.response.send_message(embed=create_embed(
                title="❌ Erro",
                description=f"{interaction.user.mention}, valor inválido.",
                color=discord.Color.red()
            ), ephemeral=True)
            return

        if amount <= 0 or amount > balance or choice < 1 or choice > 6:
            await interaction.response.send_message(embed=create_embed(
                title="❌ Erro",
                description=f"{interaction.user.mention}, valor inválido ou saldo insuficiente.",
                color=discord.Color.red()
            ), ephemeral=True)
            return

        embed = create_embed(
            title="🎲 Rolando os Dados...",
            description=f"{interaction.user.mention} está apostando **{amount} moedas** no número **{choice}**!",
            color=discord.Color.blue()
        )
        embed.set_image(url=DICE_ROLL_GIF)
        message = await interaction.response.send_message(embed=embed)

        await asyncio.sleep(3)

        result = random.randint(1, 6)
        if choice == result:
            new_balance = balance + amount * 5
            embed = create_embed(
                title="🎉 Você Ganhou!",
                description=f"Resultado: **{result}**!\n{interaction.user.mention}, você ganhou **{amount * 5} moedas**! Seu novo saldo é **{new_balance}**.",
                color=discord.Color.green()
            )
        else:
            new_balance = balance - amount
            embed = create_embed(
                title="😢 Você Perdeu!",
                description=f"Resultado: **{result}**!\n{interaction.user.mention}, você perdeu **{amount} moedas**. Seu novo saldo é **{new_balance}**.",
                color=discord.Color.red()
            )

        c.execute('UPDATE users SET balance = ? WHERE user_id = ?', (new_balance, user_id))
        log_transaction(user_id, "dice_roll", amount * 5 if choice == result else -amount)
        conn.commit()
        await interaction.edit_original_response(embed=embed)

# Modal para Roleta
class RouletteModal(discord.ui.Modal, title="Apostar em Roleta"):
    amount = discord.ui.TextInput(label="Quantidade de Moedas", placeholder="Digite a quantidade...")
    choice = discord.ui.TextInput(label="Escolha (1-36)", placeholder="Digite um número de 1 a 36...")

    async def on_submit(self, interaction: discord.Interaction):
        user_id = interaction.user.id
        c.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
        result = c.fetchone()
        if not result:
            await interaction.response.send_message(embed=create_embed(
                title="❌ Erro",
                description=f"{interaction.user.mention}, você precisa se registrar primeiro. Use `!registrar`.",
                color=discord.Color.red()
            ), ephemeral=True)
            return

        balance = result[0]
        try:
            amount = int(self.amount.value)
            choice = int(self.choice.value)
        except ValueError:
            await interaction.response.send_message(embed=create_embed(
                title="❌ Erro",
                description=f"{interaction.user.mention}, valor inválido.",
                color=discord.Color.red()
            ), ephemeral=True)
            return

        if amount <= 0 or amount > balance or choice < 1 or choice > 36:
            await interaction.response.send_message(embed=create_embed(
                title="❌ Erro",
                description=f"{interaction.user.mention}, valor inválido ou saldo insuficiente.",
                color=discord.Color.red()
            ), ephemeral=True)
            return

        embed = create_embed(
            title="🎡 Girando a Roleta...",
            description=f"{interaction.user.mention} está apostando **{amount} moedas** no número **{choice}**!",
            color=discord.Color.blue()
        )
        embed.set_image(url=ROULETTE_GIF)
        message = await interaction.response.send_message(embed=embed)

        await asyncio.sleep(3)

        result = random.randint(1, 36)
        if choice == result:
            new_balance = balance + amount * 10
            embed = create_embed(
                title="🎉 Você Ganhou!",
                description=f"Resultado: **{result}**!\n{interaction.user.mention}, você ganhou **{amount * 10} moedas**! Seu novo saldo é **{new_balance}**.",
                color=discord.Color.green()
            )
        else:
            new_balance = balance - amount
            embed = create_embed(
                title="😢 Você Perdeu!",
                description=f"Resultado: **{result}**!\n{interaction.user.mention}, você perdeu **{amount} moedas**. Seu novo saldo é **{new_balance}**.",
                color=discord.Color.red()
            )

        c.execute('UPDATE users SET balance = ? WHERE user_id = ?', (new_balance, user_id))
        log_transaction(user_id, "roulette", amount * 10 if choice == result else -amount)
        conn.commit()
        await interaction.edit_original_response(embed=embed)

# Comando para abrir o painel de controle
@bot.command(name="painel")
async def panel(ctx):
    view = ControlPanel()
    embed = create_embed(
        title="🎮 Painel de Controle",
        description="Escolha uma opção abaixo:",
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed, view=view)

# Comando para registrar um usuário
@bot.command(name="registrar")
async def register(ctx):
    user_id = ctx.author.id
    c.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    if c.fetchone() is None:
        c.execute('INSERT INTO users (user_id) VALUES (?)', (user_id,))
        conn.commit()

        # Mensagem de boas-vindas complexa
        embed = create_embed(
            title="🎉 Bem-vindo ao **Cassino do Discord**! 🎉",
            description=(
                f"Olá, {ctx.author.mention}! 👋\n\n"
                "🌟 **Você foi registrado com sucesso no nosso sistema!** 🌟\n"
                "Agora você começa com **1000 moedas** para apostar e se divertir! 💰\n\n"
                "🎮 **Como jogar?**\n"
                "1. Use o painel de controle abaixo para interagir com o bot.\n"
                "2. Escolha entre **cara ou coroa**, **dados** ou **roleta** para apostar.\n"
                "3. Acompanhe seu saldo e suba no **leaderboard**! 🏆\n\n"
                "📌 **Dicas importantes:**\n"
                "- Use `!painel` para acessar o painel de controle a qualquer momento.\n"
                "- Participe de **eventos especiais** para ganhar recompensas extras! 🎁\n\n"
                "Divirta-se e boa sorte! 🍀"
            ),
            color=discord.Color.gold()
        )
        embed.set_thumbnail(url=ctx.author.avatar.url)
        embed.set_footer(text="Cassino do Discord | Use !painel para começar!")

        # Botões interativos
        view = ControlPanel()
        await ctx.send(embed=embed, view=view)
    else:
        embed = create_embed(
            title="❌ Erro",
            description=f"{ctx.author.mention}, você já está registrado!",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)

# Comando para leaderboard
@bot.command(name="leaderboard")
async def leaderboard(ctx):
    c.execute('SELECT user_id, balance FROM users ORDER BY balance DESC LIMIT 10')
    top_users = c.fetchall()
    leaderboard_message = "**🏆 Leaderboard:**\n"
    for i, (user_id, balance) in enumerate(top_users, 1):
        user = await bot.fetch_user(user_id)
        leaderboard_message += f"{i}. {user.name} - **{balance}** moedas\n"

    embed = create_embed(
        title="🏆 Leaderboard",
        description=leaderboard_message,
        color=discord.Color.gold()
    )
    await ctx.send(embed=embed)

# Comando para criar um evento
@bot.command(name="criarevento")
@commands.has_permissions(administrator=True)
async def create_event(ctx, name: str, reward: int, duration_minutes: int):
    end_time = (datetime.now() + timedelta(minutes=duration_minutes)).strftime('%Y-%m-%d %H:%M:%S')
    c.execute('INSERT INTO events (name, reward, end_time) VALUES (?, ?, ?)', (name, reward, end_time))
    conn.commit()
    global active_event
    active_event = (name, reward, end_time)
    embed = create_embed(
        title="🎉 Evento Criado!",
        description=f"Evento **{name}** criado! Recompensa: **{reward} moedas**. Duração: **{duration_minutes} minutos**.",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)

# Comando para participar de um evento
@bot.command(name="participarevento")
async def join_event(ctx):
    global active_event
    if not active_event:
        await ctx.send(embed=create_embed(
            title="❌ Erro",
            description="Não há nenhum evento ativo no momento.",
            color=discord.Color.red()
        ))
        return

    user_id = ctx.author.id
    c.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    if not result:
        await ctx.send(embed=create_embed(
            title="❌ Erro",
            description=f"{ctx.author.mention}, você precisa se registrar primeiro. Use `!registrar`.",
            color=discord.Color.red()
        ))
        return

    new_balance = result[0] + active_event[1]
    c.execute('UPDATE users SET balance = ? WHERE user_id = ?', (new_balance, user_id))
    log_transaction(user_id, "event_reward", active_event[1])
    conn.commit()
    embed = create_embed(
        title="🎉 Participação no Evento!",
        description=f"{ctx.author.mention}, você participou do evento **{active_event[0]}** e ganhou **{active_event[1]} moedas**! Seu novo saldo é **{new_balance}**.",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)

# Comando para dar moedas (apenas para administradores)
@bot.command(name="dar")
@commands.has_permissions(administrator=True)
async def give(ctx, member: discord.Member, amount: int):
    if amount <= 0:
        await ctx.send(embed=create_embed(
            title="❌ Erro",
            description="O valor deve ser maior que zero.",
            color=discord.Color.red()
        ))
        return

    user_id = member.id
    c.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    result = c.fetchone()
    if not result:
        c.execute('INSERT INTO users (user_id, balance) VALUES (?, ?)', (user_id, amount))
    else:
        new_balance = result[0] + amount
        c.execute('UPDATE users SET balance = ? WHERE user_id = ?', (new_balance, user_id))
    log_transaction(user_id, "admin_gift", amount)
    conn.commit()
    embed = create_embed(
        title="🎁 Moedas Adicionadas",
        description=f"{member.mention} recebeu **{amount} moedas**. Novo saldo: **{new_balance}**.",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)

# Iniciar o bot
bot.run('TOKEN')
