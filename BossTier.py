import discord
from discord.ext import commands
from discord import app_commands
import datetime

# --- CẤU HÌNH ---
TOKEN = "YOUR_TOKEN"
ALLOWED_ROLES = [1517104790948151386, 1502217814994456676]

ROLE_MAP = {
    "lt5": 1502218507591483442, "ht5": 1502218544887365673,
    "lt4": 1502218563149234216, "ht4": 1502218593704607884,
    "lt3": 1502218609840361563, "ht3": 1502218664814972938,
    "lt2": 1502218679516139580, "ht2": 1502218701896683560,
    "lt1": 1517103784235634718, "ht1": 1517103994152157255
}

MODE_ICONS = {
    "Sword": "<:sword:1502223694016155718>",
    "NetheritePot": "<:nethop:1502223720826015897>",
    "SMP": "<:smp:1502223799981178880>",
    "Vanilla": "<:vanilla:1502223852741066772>",
    "Axe": "<:axe:1502223779554918420>",
    "UHC": "<:uhc:1502223752476233810>",
    "Mace": "<:mace:1502223822307332186>"
}

MODE_WAITLIST_CONFIG = {
    "Sword": {"role": 1502219398197411890, "chan": "#sword-waitlist"},
    "SMP": {"role": 1502219431034617947, "chan": "#smp-waitlist"},
    "Vanilla": {"role": 1502219496797110342, "chan": "#vanilla-waitlist"},
    "NetheritePot": {"role": 1502219524072542389, "chan": "#nethop-waitlist"},
    "Axe": {"role": 1502219631623143524, "chan": "#axe-waitlist"},
    "Mace": {"role": 1502219739555172484, "chan": "#mace-waitlist"},
    "UHC": {"role": 1502225864346177596, "chan": "#uhc-waitlist"}
}

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

queue_players = []
queue_owner = None
current_testing = None
queue_message = None
closed_message = None # Biến mới để quản lý bảng đóng

def has_permission(member): return any(role.id in ALLOWED_ROLES for role in member.roles)

def create_embed():
    embed = discord.Embed(title="🟢 Test Tier Queue Open", color=discord.Color.green())
    players_text = "\n".join(f"{i+1}. <@{uid}>" for i, uid in enumerate(queue_players)) if queue_players else "None"
    embed.add_field(name=f"👥 Players in Queue ({len(queue_players)}/20)", value=players_text, inline=False)
    embed.add_field(name="🎯 Player Testing", value=f"<@{current_testing}>" if current_testing else "None", inline=False)
    embed.add_field(name="👨‍💻 Active Testers", value=f"<@{queue_owner}>" if queue_owner else "None", inline=False)
    embed.set_footer(text="Sử dụng nút Join Queue để tham gia test tier.")
    return embed

# --- Các class View giữ nguyên ---
class ModeSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        options = [discord.SelectOption(label=m, value=m) for m in MODE_WAITLIST_CONFIG.keys()]
        select = discord.ui.Select(placeholder="Chọn mode...", options=options, custom_id="mode_select_waitlist")
        async def callback(i: discord.Interaction):
            mode = select.values[0]
            role = i.guild.get_role(MODE_WAITLIST_CONFIG[mode]["role"])
            if role:
                await i.user.add_roles(role)
                await i.response.send_message(f"✅ Bạn đã được thêm vào {MODE_WAITLIST_CONFIG[mode]['chan']}", ephemeral=True)
        select.callback = callback
        self.add_item(select)

class VerifyModal(discord.ui.Modal, title="Verify Account"):
    ign = discord.ui.TextInput(label="In-game name (IGN)", placeholder="Nhập IGN của bạn")
    async def on_submit(self, i: discord.Interaction):
        try:
            current_nick = i.user.nick or i.user.name
            base_name = current_nick.split(' | ')[0]
            new_nick = f"{base_name} | {self.ign.value}"
            await i.user.edit(nick=new_nick)
            await i.response.send_message(f"✅ Đã cập nhật tên thành: {new_nick}", ephemeral=True)
        except Exception:
            await i.response.send_message("❌ Lỗi: Bot không có quyền đổi tên.", ephemeral=True)

class MainMenuView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Verify Account", style=discord.ButtonStyle.primary, custom_id="btn_verify")
    async def v(self, i, b): await i.response.send_modal(VerifyModal())
    @discord.ui.button(label="Enter Waitlist", style=discord.ButtonStyle.success, custom_id="btn_waitlist")
    async def w(self, i, b): await i.response.send_message("Chọn mode:", view=ModeSelectView(), ephemeral=True)

class ConfirmCloseView(discord.ui.View):
    def __init__(self): super().__init__(timeout=60)
    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        global current_testing
        current_testing = None
        if queue_message: await queue_message.edit(embed=create_embed())
        await interaction.response.send_message("✅ Đã đóng ticket.")
        await interaction.channel.delete()

class TicketView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.secondary)
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not has_permission(interaction.user): return await interaction.response.send_message("❌ No permission", ephemeral=True)
        await interaction.response.send_message("⚠️ Chắc chắn đóng ticket?", view=ConfirmCloseView(), ephemeral=True)

class QueueView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Join Queue", style=discord.ButtonStyle.green, custom_id="btn_join")
    async def join_queue(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id not in queue_players:
            queue_players.append(interaction.user.id)
            await interaction.response.edit_message(embed=create_embed(), view=self)
    @discord.ui.button(label="Leave Queue", style=discord.ButtonStyle.red, custom_id="btn_leave")
    async def leave_queue(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id in queue_players:
            queue_players.remove(interaction.user.id)
            await interaction.response.edit_message(embed=create_embed(), view=self)

@bot.event
async def on_ready():
    bot.add_view(MainMenuView())
    bot.add_view(ModeSelectView())
    bot.add_view(QueueView())
    await bot.tree.sync()
    print(f"✅ Bot đã sẵn sàng: {bot.user}")

@bot.tree.command(name="setup-menu", description="Gửi menu chính để xác minh và vào danh sách chờ")
async def setup_menu(i: discord.Interaction):
    description_text = (
        "Chào mừng bạn! Vui lòng chọn Xác minh tài khoản hoặc vào Waitlists :\n"
        "- **Verify**: là bạn sẽ nhập tên của bạn vào và ấn enter\n"
        "- **Enter Waitlists**: là bạn sẽ chọn mode bạn muốn vào để chờ queue"
    )
    embed = discord.Embed(title="📝 Evaluation Testing Waitlist", description=description_text, color=discord.Color.dark_gray())
    await i.response.send_message(embed=embed, view=MainMenuView())

# --- LỆNH MỚI ĐÃ CHỈNH SỬA ---
@bot.tree.command(name="open-queue", description="Mở hàng đợi")
async def open_queue(interaction: discord.Interaction):
    global queue_owner, queue_players, queue_message, closed_message
    if not has_permission(interaction.user): return await interaction.response.send_message("❌ No permission", ephemeral=True)

    # Xóa bảng đóng cũ nếu có
    if closed_message:
        try: await closed_message.delete()
        except: pass
        closed_message = None

    queue_owner = interaction.user.id
    queue_players = []
    await interaction.response.send_message(content="@here", embed=create_embed(), view=QueueView())
    queue_message = await interaction.original_response()

@bot.tree.command(name="close-queue", description="Đóng queue và thông báo kết thúc")
async def close_queue(interaction: discord.Interaction):
    global queue_owner, queue_players, current_testing, queue_message

    if not has_permission(interaction.user):
        return await interaction.response.send_message("❌ Bạn không có quyền!", ephemeral=True)

    # Tạo Embed thông báo kết thúc
    ended_embed = discord.Embed(
        title="🚫 No Testers Online 🚫",
        description="No testers for neth currently\nYou will be pinged when a tester is ready.",
        color=discord.Color.red()
    )
    ended_embed.add_field(
        name="Session Ended",
        value=f"<t:{int(discord.utils.utcnow().timestamp())}:f>", # Hiển thị thời gian thực
        inline=False
    )
    ended_embed.set_footer(text="Ended just now")

    # Xóa tin nhắn queue cũ nếu tồn tại
    if queue_message:
        try:
            await queue_message.delete()
        except:
            pass

    # Gửi thông báo kết thúc mới
    await interaction.channel.send(embed=ended_embed)

    # Reset toàn bộ trạng thái
    queue_owner = None
    queue_players = []
    current_testing = None
    queue_message = None

    await interaction.response.send_message("✅ Đã đóng queue thành công.", ephemeral=True)


    queue_owner = None; queue_players = []; current_testing = None
    await interaction.response.send_message("✅ Đã đóng queue.", ephemeral=True)

@bot.tree.command(name="nextplayer", description="Chọn người chơi tiếp theo")
async def nextplayer(interaction: discord.Interaction, player: discord.Member):
    global current_testing
    if not has_permission(interaction.user): return await interaction.response.send_message("❌ No permission", ephemeral=True)
    if player.id not in queue_players: return await interaction.response.send_message("❌ Không có trong queue", ephemeral=True)
    queue_players.remove(player.id); current_testing = player.id
    if queue_message: await queue_message.edit(embed=create_embed())
    channel = await interaction.guild.create_text_channel(f"ticket-{player.name}")
    await channel.send(f"{player.mention} sẵn sàng! Tester: {interaction.user.mention}", view=TicketView())
    await interaction.response.send_message(f"✅ Đã tạo ticket: {channel.mention}", ephemeral=True)

# ... (Giữ nguyên hàm results)
@bot.tree.command(name="results", description="Ghi nhận kết quả sau khi kiểm tra xong")
@app_commands.choices(mode=[app_commands.Choice(name=m, value=m) for m in MODE_ICONS.keys()],
                      tier_before=[app_commands.Choice(name=r, value=r) for r in ROLE_MAP.keys()],
                      tier_earned=[app_commands.Choice(name=r, value=r) for r in ROLE_MAP.keys()])
async def results(interaction: discord.Interaction, user: discord.Member, tier_before: str, tier_earned: str, username: str, mode: str):
    if not has_permission(interaction.user): return await interaction.response.send_message("❌ No permission", ephemeral=True)
    await interaction.response.defer()
    embed = discord.Embed(title=f"{user.display_name}'s Test Result", color=discord.Color.dark_gray())
    thumbnail_url = f"https://render.crafty.gg/3d/bust/{username}"
    embed.set_thumbnail(url=thumbnail_url)
    embed.add_field(name="Tester", value=f"{interaction.user.mention}", inline=False)
    embed.add_field(name="Username", value=username, inline=False)
    embed.add_field(name="Mode", value=f"{MODE_ICONS.get(mode, '')} {mode}", inline=False)
    embed.add_field(name="Previous Rank", value=tier_before.upper(), inline=False)
    embed.add_field(name="Rank Earned", value=tier_earned.upper(), inline=False)
    await interaction.followup.send(content=f"{user.mention}", embed=embed)
    new_role = interaction.guild.get_role(ROLE_MAP[tier_earned])
    if new_role:
        old_roles = [r for r in user.roles if r.id in ROLE_MAP.values()]
        await user.remove_roles(*old_roles)
        await user.add_roles(new_role)
bot.run(TOKEN)
