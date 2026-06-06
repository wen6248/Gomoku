#'''创作者：wen'''

import tkinter
from tkinter import messagebox, Tk, Canvas, StringVar, Label, Button, Frame, Entry
import tkinter.simpledialog
import math
import socket
import threading
import json
import time
import random


# ========================= 可自由缩放的棋盘类 =========================
class ChessBoard:
    def __init__(self, parent_frame, on_resize_callback):
        self.parent = parent_frame
        self.on_resize = on_resize_callback
        self.canvas = Canvas(parent_frame, bg="#E3C16F", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.cell_size = 30
        self.margin = 25
        self.size = 15
        # 绑定尺寸变化事件
        self.canvas.bind("<Configure>", self._on_configure)
        # 初始绘制
        self.canvas.after(50, self._force_redraw)

    def _on_configure(self, event=None):
        """窗口尺寸变化时重新计算并绘制棋盘"""
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 50 or h < 50:
            return
        # 计算合适的边距和格子大小，保持正方形棋盘
        min_side = min(w, h)
        self.margin = max(20, int(min_side * 0.06))
        available = min_side - 2 * self.margin
        self.cell_size = available / (self.size - 1)
        self.paint_board()
        if self.on_resize:
            self.on_resize()

    def _force_redraw(self):
        self._on_configure()

    def paint_board(self):
        self.canvas.delete("board")
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        # 绘制木质背景纹理（简单模拟）
        self.canvas.create_rectangle(0, 0, w, h, fill="#E3C16F", outline="", tags="board")
        # 绘制边框
        board_px = self.margin + (self.size - 1) * self.cell_size
        self.canvas.create_rectangle(
            self.margin, self.margin, board_px, board_px,
            outline="#5D4037", width=3, tags="board"
        )
        # 绘制网格线
        for i in range(self.size):
            pos = self.margin + i * self.cell_size
            # 横线
            width = 2 if i == 0 or i == self.size - 1 else 1
            self.canvas.create_line(
                self.margin, pos, board_px, pos,
                fill="#3E2723", width=width, tags="board"
            )
            # 竖线
            self.canvas.create_line(
                pos, self.margin, pos, board_px,
                fill="#3E2723", width=width, tags="board"
            )
        # 星位
        stars = [(3, 3), (11, 3), (3, 11), (11, 11), (7, 7)]
        r = max(3, self.cell_size * 0.12)
        for sx, sy in stars:
            cx = self.margin + sx * self.cell_size
            cy = self.margin + sy * self.cell_size
            self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                                    fill="#3E2723", outline="", tags="board")

    def get_cell_pos(self, row, col):
        """根据行列返回像素坐标"""
        x = self.margin + col * self.cell_size
        y = self.margin + row * self.cell_size
        return x, y

    def get_cell_from_pixel(self, px, py):
        """根据像素坐标返回最近的行列"""
        x = (px - self.margin) / self.cell_size
        y = (py - self.margin) / self.cell_size
        col = round(x)
        row = round(y)
        # 边界检查
        row = max(0, min(self.size - 1, row))
        col = max(0, min(self.size - 1, col))
        return row, col

    def draw_chessman(self, row, col, color, tag="chessman"):
        """绘制棋子，返回画布对象id"""
        x, y = self.get_cell_pos(row, col)
        r = max(8, self.cell_size * 0.38)
        # 阴影效果（使用偏移的深色椭圆模拟）
        shadow_r = r + 1
        shadow_color = "#555555" if color == "white" else "#222222"
        self.canvas.create_oval(
            x - shadow_r + 2, y - shadow_r + 3,
            x + shadow_r + 2, y + shadow_r + 3,
            fill=shadow_color, outline="", tags=tag
        )
        # 棋子本体
        oid = self.canvas.create_oval(
            x - r, y - r, x + r, y + r,
            fill=color, outline="#333" if color == "white" else "#111",
            width=1, tags=tag
        )
        # 高光效果
        hl_r = r * 0.35
        hl_x = x - r * 0.25
        hl_y = y - r * 0.25
        hl_color = "#888888" if color == "black" else "#FFFFFF"
        self.canvas.create_oval(
            hl_x - hl_r, hl_y - hl_r,
            hl_x + hl_r, hl_y + hl_r,
            fill=hl_color, outline="", tags=tag
        )
        return oid

    def draw_last_move_marker(self, row, col, tag="marker"):
        """绘制最后落子标记（小红点）"""
        x, y = self.get_cell_pos(row, col)
        r = max(3, self.cell_size * 0.12)
        self.canvas.create_oval(
            x - r, y - r, x + r, y + r,
            fill="red", outline="", tags=tag
        )

    def draw_win_line(self, cells, tag="winline"):
        """绘制胜利连线"""
        if not cells:
            return
        x1, y1 = self.get_cell_pos(cells[0][0], cells[0][1])
        x2, y2 = self.get_cell_pos(cells[-1][0], cells[-1][1])
        self.canvas.create_line(
            x1, y1, x2, y2,
            fill="#FF5722", width=max(3, self.cell_size * 0.15),
            tags=tag
        )


# ========================= 高级AI引擎 =========================
class GobangAI:
    def __init__(self, db):
        self.db = db
        self.size = 15
        # 棋型分数（调整为更合理的数值）
        self.score_map = {
            "five": 1000000,  # 五连
            "live4": 100000,  # 活四
            "dead4": 8000,  # 冲四
            "live3": 7000,  # 活三
            "sleep3": 2500,  # 眠三
            "live2": 1500,  # 活二
            "sleep2": 400,  # 眠二
            "one": 50  # 单棋
        }
        # 预计算方向
        self.dirs = [(1, 0), (0, 1), (1, 1), (1, -1)]

    def is_empty(self, y, x):
        """检查坐标是否为空且在棋盘内"""
        return 0 <= y < self.size and 0 <= x < self.size and self.db[y][x] == 2

    def is_color(self, y, x, color):
        """检查坐标是否为指定颜色棋子"""
        return 0 <= y < self.size and 0 <= x < self.size and self.db[y][x] == color

    def get_line(self, y, x, dy, dx, color):
        """获取一条线上连续同色棋子及两端状态"""
        line = []
        cy, cx = y + dy, x + dx
        while 0 <= cy < self.size and 0 <= cx < self.size:
            if self.db[cy][cx] == color:
                line.append(1)
            elif self.db[cy][cx] == 2:
                line.append(0)
                break  # 遇到空位就停止
            else:
                line.append(-1)
                break  # 遇到对方棋子停止
            cy += dy
            cx += dx
        return line

    def analyze_direction(self, y, x, dy, dx, color):
        """分析某一方向的棋型，返回(连续数, 左开放, 右开放, 左空格数, 右空格数)"""
        # 正向（dy, dx）
        line1 = self.get_line(y, x, dy, dx, color)
        # 反向（-dy, -dx）
        line2 = self.get_line(y, x, -dy, -dx, color)

        # 统计连续棋子数
        cnt = 1
        # 统计正向连续数
        for val in line1:
            if val == 1:
                cnt += 1
            else:
                break
        # 统计反向连续数
        for val in line2:
            if val == 1:
                cnt += 1
            else:
                break

        # 检查两端是否开放（有空格）
        left_open = len(line2) > 0 and line2[0] == 0
        right_open = len(line1) > 0 and line1[0] == 0

        # 计算空格数
        left_space = 0
        if left_open:
            left_space = 1
            for val in line2[1:]:
                if val == 0:
                    left_space += 1
                else:
                    break

        right_space = 0
        if right_open:
            right_space = 1
            for val in line1[1:]:
                if val == 0:
                    right_space += 1
                else:
                    break

        return cnt, left_open, right_open, left_space, right_space

    def eval_direction(self, y, x, dy, dx, color):
        """评估单一方向的分数"""
        cnt, left_open, right_open, ls, rs = self.analyze_direction(y, x, dy, dx, color)

        # 五连
        if cnt >= 5:
            return self.score_map["five"]

        # 活四 / 冲四
        if cnt == 4:
            if left_open and right_open:
                return self.score_map["live4"]
            elif left_open or right_open:
                return self.score_map["dead4"]

        # 活三 / 眠三
        if cnt == 3:
            if left_open and right_open:
                return self.score_map["live3"]
            elif left_open or right_open:
                return self.score_map["sleep3"]

        # 跳活三 (如 _OO_O_)
        if cnt == 2 and left_open and right_open:
            # 检查是否有跳连的可能
            total_space = ls + rs
            if total_space >= 2:
                # 检查中间是否有一个空格可以形成活三
                return self.score_map["live3"] * 0.8

        # 活二 / 眠二
        if cnt == 2:
            if left_open and right_open:
                return self.score_map["live2"]
            elif left_open or right_open:
                return self.score_map["sleep2"]

        # 单个棋子
        if cnt == 1:
            if left_open and right_open:
                return self.score_map["one"] * 2
            elif left_open or right_open:
                return self.score_map["one"]

        return self.score_map["one"] * cnt

    def evaluate_point(self, y, x, ai_color, player_color):
        """评估一个落子点的综合分数（进攻+防守）"""
        if not self.is_empty(y, x):
            return -1

        # 进攻分：AI落子在这里
        self.db[y][x] = ai_color
        attack = sum(self.eval_direction(y, x, dy, dx, ai_color) for dy, dx in self.dirs)

        # 检查AI落子后是否直接获胜
        if self.check_win_fast(y, x, ai_color):
            attack += self.score_map["five"]

        # 防守分：玩家落子在这里（阻止玩家）
        self.db[y][x] = player_color
        defense = sum(self.eval_direction(y, x, dy, dx, player_color) for dy, dx in self.dirs)

        # 恢复空位
        self.db[y][x] = 2

        # 防守权重略高，避免被冲四等杀死
        return attack + defense * 1.2

    def get_candidate_moves(self, radius=2):
        """获取候选落子点：只考虑已有棋子附近的空位"""
        candidates = set()
        has_stone = False

        # 遍历所有已有棋子
        for y in range(self.size):
            for x in range(self.size):
                if self.db[y][x] != 2:
                    has_stone = True
                    # 只考虑周围radius范围内的空位
                    for dy in range(-radius, radius + 1):
                        for dx in range(-radius, radius + 1):
                            ny, nx = y + dy, x + dx
                            if self.is_empty(ny, nx):
                                candidates.add((ny, nx))

        # 如果棋盘为空，下在天元
        if not has_stone:
            return [(7, 7)]

        # 转换为列表并去重
        candidates_list = list(candidates)
        # 对候选点进行随机排序，避免AI总是下在同一个位置
        random.shuffle(candidates_list)
        return candidates_list

    def check_win_fast(self, y, x, color):
        """快速检查某点是否形成五连"""
        for dy, dx in self.dirs:
            cnt = 1
            # 正向
            cy, cx = y + dy, x + dx
            while self.is_color(cy, cx, color):
                cnt += 1
                cy += dy
                cx += dx
            # 反向
            cy, cx = y - dy, x - dx
            while self.is_color(cy, cx, color):
                cnt += 1
                cy -= dy
                cx -= dx
            if cnt >= 5:
                return True
        return False

    def ai_get_pos(self, ai_color, player_color, depth=2):
        """AI计算最优落子，使用Minimax+Alpha-Beta"""
        # 获取候选落子点
        candidates = self.get_candidate_moves(radius=2)
        if not candidates:
            return 7, 7

        # 第一步直接评分找最佳（简单模式）
        if depth <= 1:
            best_score = -float('inf')
            best_pos = candidates[0]

            for y, x in candidates:
                if not self.is_empty(y, x):
                    continue

                # 评估该点分数
                score = self.evaluate_point(y, x, ai_color, player_color)

                # 如果找到必胜点，直接返回
                if score >= self.score_map["five"]:
                    return y, x

                if score > best_score:
                    best_score = score
                    best_pos = (y, x)

            return best_pos

        # Minimax搜索（depth=2，考虑玩家回应）
        best_score = -float('inf')
        best_pos = candidates[0]

        for y, x in candidates:
            if not self.is_empty(y, x):
                continue

            # 模拟AI落子
            self.db[y][x] = ai_color

            # 检查AI是否直接获胜
            if self.check_win_fast(y, x, ai_color):
                self.db[y][x] = 2
                return y, x

            # 评估玩家的最佳回应
            player_best_score = -float('inf')
            player_candidates = self.get_candidate_moves(radius=2)

            for py, px in player_candidates:
                if not self.is_empty(py, px):
                    continue

                # 模拟玩家落子
                self.db[py][px] = player_color

                # 计算玩家落子的分数
                player_score = self.evaluate_point(py, px, player_color, ai_color)

                # 检查玩家是否会获胜
                if self.check_win_fast(py, px, player_color):
                    player_score += self.score_map["five"]

                # 更新玩家最佳分数
                if player_score > player_best_score:
                    player_best_score = player_score

                # 恢复玩家落子
                self.db[py][px] = 2

            # 恢复AI落子
            self.db[y][x] = 2

            # 计算当前点的最终分数（AI得分 - 玩家最佳回应得分）
            current_score = self.evaluate_point(y, x, ai_color, player_color) - player_best_score * 0.8

            # 更新AI最佳落子
            if current_score > best_score:
                best_score = current_score
                best_pos = (y, x)

        # 确保返回的位置有效
        if not self.is_empty(best_pos[0], best_pos[1]):
            # 如果最佳位置被占用，重新找一个有效的位置
            for pos in candidates:
                if self.is_empty(pos[0], pos[1]):
                    best_pos = pos
                    break

        return best_pos


# ========================= 五子棋主游戏类 =========================
class Gobang:
    def __init__(self):
        self.window = Tk()
        self.window.title("五子棋 - 智能AI对战 & 局域网联机")
        self.window.geometry("900x650")
        self.window.minsize(600, 450)
        self.window.configure(bg="#F5F5DC")

        # 数据初始化
        self.db = [[2] * 15 for _ in range(15)]  # 2表示空，0表示黑，1表示白
        self.order = []  # 落子顺序
        self.color_count = 0  # 0:黑，1:白
        self.color = 'black'
        self.flag_win = 1  # 1:未结束，0:游戏中
        self.flag_empty = 1  # 1:空棋盘，0:有棋子
        self.last_move = None  # 最后落子位置
        self.win_line_cells = []  # 胜利连线

        # 模式控制
        self.game_mode = StringVar(value="local")
        self.net_sock = None
        self.net_is_server = False
        self.net_running = False
        self.net_my_color = 0
        self.net_wait = False
        self.net_peer_name = ""

        # 初始化AI
        self.ai = GobangAI(self.db)

        # 构建UI
        self._build_ui()
        self.board.canvas.bind("<Button-1>", self.chess_moving)
        self.window.mainloop()

    def _build_ui(self):
        """构建主界面布局"""
        # 主框架
        main_frame = Frame(self.window, bg="#F5F5DC")
        main_frame.pack(fill="both", expand=True, padx=5, pady=5)

        # 左侧棋盘区域
        board_frame = Frame(main_frame, bg="#8D6E63", bd=2, relief="ridge")
        board_frame.pack(side="left", fill="both", expand=True, padx=5, pady=5)

        self.board = ChessBoard(board_frame, on_resize_callback=self._redraw_chessmen)

        # 右侧控制面板
        ctrl_frame = Frame(main_frame, bg="#FFF8E1", width=260, bd=2, relief="groove")
        ctrl_frame.pack(side="right", fill="y", padx=5, pady=5)
        ctrl_frame.pack_propagate(False)

        # 标题
        Label(ctrl_frame, text="五子棋", font=("Microsoft YaHei", 20, "bold"),
              bg="#FFF8E1", fg="#3E2723").pack(pady=(15, 5))

        # 状态显示
        self.game_print = StringVar(value="请选择模式并开始")
        self.status_label = Label(ctrl_frame, textvariable=self.game_print,
                                  font=("Microsoft YaHei", 12), bg="#FFF8E1",
                                  fg="#D84315", wraplength=230)
        self.status_label.pack(pady=5)

        # 模式选择
        mode_frame = Frame(ctrl_frame, bg="#FFF8E1")
        mode_frame.pack(pady=10, padx=10, fill="x")
        Label(mode_frame, text="游戏模式", font=("Microsoft YaHei", 11, "bold"),
              bg="#FFF8E1", fg="#5D4037").pack(anchor="w")

        for text, val, color in [
            ("双人本地对战", "local", "#4CAF50"),
            ("人机对战 (AI)", "ai", "#2196F3"),
            ("局域网联机", "net", "#FF9800")
        ]:
            rb = tkinter.Radiobutton(mode_frame, text=text, variable=self.game_mode,
                                     value=val, font=("Microsoft YaHei", 10),
                                     bg="#FFF8E1", activebackground="#FFF8E1",
                                     selectcolor=color, command=self._on_mode_change)
            rb.pack(anchor="w", pady=2)

        # 联机控制区
        self.net_frame = Frame(ctrl_frame, bg="#FFF3E0", bd=1, relief="solid")
        self.net_frame.pack(pady=5, padx=10, fill="x")
        self.net_frame_visible = False
        self._build_net_ui()

        # 功能按钮区
        btn_frame = Frame(ctrl_frame, bg="#FFF8E1")
        btn_frame.pack(pady=10, padx=10, fill="x")

        btn_style = {"font": ("Microsoft YaHei", 10), "width": 12,
                     "bg": "#5D4037", "fg": "white", "activebackground": "#4E342E",
                     "activeforeground": "white", "bd": 0, "cursor": "hand2"}

        Button(btn_frame, text="开始游戏", command=self.game_start, **btn_style).pack(pady=3)
        Button(btn_frame, text="悔棋", command=self.withdraw, **btn_style).pack(pady=3)
        Button(btn_frame, text="停走一步", command=self.take_a_stop, **btn_style).pack(pady=3)
        Button(btn_frame, text="清空棋局", command=self.empty_all,
               **{**btn_style, "bg": "#795548"}).pack(pady=3)
        Button(btn_frame, text="认输", command=self.ren_shu,
               **{**btn_style, "bg": "#BF360C"}).pack(pady=3)
        Button(btn_frame, text="游戏规则", command=self.rules_of_the_game,
               **{**btn_style, "bg": "#455A64"}).pack(pady=3)
        Button(btn_frame, text="结束游戏", command=self.window.destroy,
               **{**btn_style, "bg": "#263238"}).pack(pady=3)

        # 底部信息
        Label(ctrl_frame, text="v2.0 | 支持缩放窗口", font=("Arial", 9),
              bg="#FFF8E1", fg="#9E9E9E").pack(side="bottom", pady=10)

    def _build_net_ui(self):
        """构建联机控制子UI"""
        for w in self.net_frame.winfo_children():
            w.destroy()
        Label(self.net_frame, text="联机设置", font=("Microsoft YaHei", 10, "bold"),
              bg="#FFF3E0", fg="#E65100").pack(pady=(5, 2))

        # 本机IP显示
        self.local_ip_var = StringVar(value="IP: 获取中...")
        Label(self.net_frame, textvariable=self.local_ip_var, font=("Arial", 9),
              bg="#FFF3E0", fg="#333").pack()
        self._update_local_ip()

        # 服务端按钮
        Button(self.net_frame, text="开启服务端", command=self.net_server_start,
               font=("Microsoft YaHei", 9), bg="#66BB6A", fg="white", bd=0,
               cursor="hand2", width=14).pack(pady=3)

        # 客户端连接
        conn_frame = Frame(self.net_frame, bg="#FFF3E0")
        conn_frame.pack(pady=2)
        Label(conn_frame, text="IP:", font=("Arial", 9), bg="#FFF3E0").pack(side="left")
        self.ip_entry = Entry(conn_frame, font=("Arial", 9), width=12, justify="center")
        self.ip_entry.pack(side="left", padx=2)
        self.ip_entry.insert(0, "127.0.0.1")
        Button(conn_frame, text="连接", command=self.net_client_connect,
               font=("Microsoft YaHei", 9), bg="#42A5F5", fg="white", bd=0,
               cursor="hand2", width=6).pack(side="left")

        # 连接状态
        self.net_status_var = StringVar(value="未连接")
        Label(self.net_frame, textvariable=self.net_status_var, font=("Arial", 9),
              bg="#FFF3E0", fg="#999").pack(pady=2)

    def _update_local_ip(self):
        """获取并显示本机局域网IP"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
        except:
            ip = "无法获取"
        self.local_ip_var.set(f"本机IP: {ip}")

    def _on_mode_change(self):
        """模式切换时更新UI"""
        mode = self.game_mode.get()
        if mode == "net":
            if not self.net_frame_visible:
                self.net_frame.pack(pady=5, padx=10, fill="x", before=self.net_frame.master.winfo_children()[2])
                self.net_frame_visible = True
        else:
            if self.net_frame_visible:
                self.net_frame.pack_forget()
                self.net_frame_visible = False

    def _redraw_chessmen(self):
        """窗口缩放后重绘所有棋子和标记"""
        self.board.canvas.delete("chessman")
        self.board.canvas.delete("marker")
        self.board.canvas.delete("winline")
        self.board.paint_board()

        # 重绘所有棋子
        for idx in self.order:
            x = idx % 15
            y = idx // 15
            color_idx = self.db[y][x]
            fill_c = "black" if color_idx == 0 else "white"
            self.board.draw_chessman(y, x, fill_c)

        # 绘制最后落子标记
        if self.last_move and self.flag_win == 0:
            ly, lx = self.last_move
            self.board.draw_last_move_marker(ly, lx)

        # 绘制胜利连线
        if self.win_line_cells and self.flag_win == 1:
            self.board.draw_win_line(self.win_line_cells)

    # -------------------------- 基础函数 --------------------------
    def change_color(self):
        """切换当前落子颜色"""
        self.color_count = (self.color_count + 1) % 2
        self.color = "black" if self.color_count == 0 else "white"

    def limit_boarder(self, y, x):
        """边界检查"""
        return 0 <= x <= 14 and 0 <= y <= 14

    def chessman_count(self, y, x, color_count):
        """统计四个方向最大连子数，并记录胜利连线"""
        counts = []
        lines = []
        # 横 纵 斜/ 斜\
        for dy, dx in [(0, 1), (1, 0), (1, 1), (1, -1)]:
            cells = [(y, x)]
            cnt = 1

            # 正向
            cy, cx = y + dy, x + dx
            while self.limit_boarder(cy, cx) and self.db[cy][cx] == color_count:
                cnt += 1
                cells.append((cy, cx))
                cy += dy
                cx += dx

            # 反向
            cy, cx = y - dy, x - dx
            while self.limit_boarder(cy, cx) and self.db[cy][cx] == color_count:
                cnt += 1
                cells.insert(0, (cy, cx))
                cy -= dy
                cx -= dx

            counts.append(cnt)
            lines.append(cells)

        max_cnt = max(counts)
        if max_cnt >= 5:
            self.win_line_cells = lines[counts.index(max_cnt)]
        return max_cnt

    def game_win(self, y, x, color_count):
        """判断是否获胜"""
        if self.chessman_count(y, x, color_count) >= 5:
            self.flag_win = 1
            self.flag_empty = 0
            return True
        return False

    def withdraw(self):
        """悔棋功能"""
        if len(self.order) == 0 or self.flag_win == 1 or self.game_mode.get() == "net":
            if self.game_mode.get() == "net":
                messagebox.showwarning("提示", "联机模式无法悔棋！")
            return

        # AI模式：需要回退两步（玩家+AI）
        steps = 2 if self.game_mode.get() == "ai" and len(self.order) >= 2 else 1

        for _ in range(steps):
            if not self.order:
                break
            z = self.order.pop()
            x = z % 15
            y = z // 15
            self.db[y][x] = 2

        # 重置状态
        self.color_count = 0
        self.color = "black"
        self.last_move = None
        self.win_line_cells = []
        self.flag_win = 1
        self.flag_empty = 1
        self._redraw_chessmen()
        self.game_print.set("已悔棋，请点击开始游戏继续")

    def empty_all(self):
        """清空棋局"""
        # 关闭网络连接
        if self.net_sock:
            self.net_running = False
            try:
                self.net_sock.close()
            except:
                pass
            self.net_sock = None
        self.net_status_var.set("未连接")

        # 清空画布
        self.board.canvas.delete("chessman")
        self.board.canvas.delete("marker")
        self.board.canvas.delete("winline")

        # 重置游戏状态
        self.db = [[2] * 15 for _ in range(15)]
        self.order = []
        self.color_count = 0
        self.color = "black"
        self.flag_win = 1
        self.flag_empty = 1
        self.last_move = None
        self.win_line_cells = []
        self.net_wait = False
        self.game_print.set("棋局已清空")

    def rules_of_the_game(self):
        """显示游戏规则"""
        msg = """游戏规则：
1. 双人本地：黑棋先行，两人轮流落子
2. AI人机对战：你执黑先手，AI执白自动落子
3. 局域网联机：一台开服务端，另一台客户端连接
4. 率先横/竖/斜连成5子即获胜
5. 窗口可自由缩放，棋盘自动适应大小"""
        messagebox.showinfo("游戏规则", msg)

    def take_a_stop(self):
        """停走一步"""
        if self.flag_win == 1 or self.game_mode.get() == "net":
            return
        self.change_color()
        self.game_print.set(f"请{self.color}落子")

    def game_start(self):
        """开始游戏"""
        if self.flag_empty == 0:
            return

        # 重置游戏状态
        self.flag_win = 0
        self.color_count = 0
        self.color = "black"
        self.win_line_cells = []
        self.last_move = None
        self._redraw_chessmen()

        mode = self.game_mode.get()
        if mode == "ai":
            self.game_print.set("你执黑先行，请点击棋盘落子")
        elif mode == "net":
            if not self.net_sock:
                messagebox.showwarning("提示", "请先建立联机连接！")
                return
            if self.net_my_color == 1:
                self.net_wait = True
                self.game_print.set("等待黑方落子...")
            else:
                self.net_wait = False
                self.game_print.set("轮到你落子（黑棋）")
        else:
            self.game_print.set("请黑方落子")

    def ren_shu(self):
        """认输"""
        if self.flag_win == 1:
            return
        winner = "white" if self.color == "black" else "black"
        self.game_print.set(f"{winner}获胜（认输）")
        self.flag_win = 1
        self.flag_empty = 0
        if self.game_mode.get() == "net" and self.net_sock:
            self._net_send({"type": "giveup"})

    # -------------------------- 落子主逻辑 --------------------------
    def chess_moving(self, event):
        """处理鼠标落子事件"""
        # 检查游戏状态
        if self.flag_win == 1 or self.flag_empty == 0:
            return

        # 联机模式检查回合
        if self.game_mode.get() == "net" and self.net_wait:
            messagebox.showinfo("等待", "现在不是你的落子回合！")
            return

        # 获取落子位置
        row, col = self.board.get_cell_from_pixel(event.x, event.y)

        # 检查位置合法性
        if not self.limit_boarder(row, col) or self.db[row][col] != 2:
            return

        # 执行落子
        self.do_chess(row, col, self.color_count)
        self.last_move = (row, col)
        self._redraw_chessmen()

        # 判断胜利
        if self.game_win(row, col, self.color_count):
            self.game_print.set(f"{self.color}获胜！")
            self._redraw_chessmen()
            if self.game_mode.get() == "net":
                self._net_send({"type": "win", "y": row, "x": col})
            return

        # 根据不同模式处理后续逻辑
        mode = self.game_mode.get()
        if mode == "ai":
            # AI模式：AI自动落子
            self.change_color()
            self.game_print.set("AI思考中...")
            self.window.update_idletasks()  # 更新界面

            # AI计算最佳落子位置
            ai_y, ai_x = self.ai.ai_get_pos(ai_color=1, player_color=0, depth=2)

            # 确保AI落子位置有效
            if self.db[ai_y][ai_x] == 2:
                # 执行AI落子
                self.do_chess(ai_y, ai_x, 1)
                self.last_move = (ai_y, ai_x)
                self._redraw_chessmen()

                # 检查AI是否获胜
                if self.game_win(ai_y, ai_x, 1):
                    self.game_print.set("AI(白棋)获胜！")
                    self._redraw_chessmen()
                    return

            # 切换回玩家回合
            self.change_color()
            self.game_print.set("请你(黑棋)落子")

        elif mode == "net":
            # 联机模式：发送落子信息
            self.change_color()
            self.net_wait = True
            self.game_print.set("等待对手落子...")
            self._net_send({"type": "move", "y": row, "x": col, "c": self.color_count})

        else:
            # 本地双人模式：切换回合
            self.change_color()
            self.game_print.set(f"请{self.color}落子")

    def do_chess(self, y, x, color_idx):
        """执行落子操作"""
        if self.db[y][x] == 2:  # 确保位置为空
            self.db[y][x] = color_idx
            self.order.append(x + 15 * y)

    # -------------------------- 网络功能 --------------------------
    def _net_send(self, data):
        """线程安全地发送网络消息（使用换行分隔JSON）"""
        if not self.net_sock:
            return
        try:
            msg = json.dumps(data, ensure_ascii=False) + "\n"
            self.net_sock.send(msg.encode("utf-8"))
        except Exception as e:
            print(f"发送失败: {e}")
            self.window.after(0, lambda: self._handle_net_disconnect())

    def net_server_start(self):
        """开启服务端"""
        if self.net_sock:
            messagebox.showwarning("提示", "已有网络连接，请清空棋局重试！")
            return

        self.net_is_server = True
        self.net_my_color = 0

        # 创建服务器套接字
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            server.bind(("0.0.0.0", 8899))
        except Exception as e:
            messagebox.showerror("错误", f"端口被占用: {e}")
            return

        server.listen(1)
        self.net_status_var.set("等待连接...")
        self.game_print.set("服务端已开启，等待客户端...")

        def accept_thread():
            """接受连接线程"""
            try:
                conn, addr = server.accept()
                self.net_sock = conn
                self.net_running = True
                self.net_status_var.set(f"已连接: {addr[0]}")
                self.game_print.set("客户端已连接！点击开始游戏")
                self.window.after(0, lambda: messagebox.showinfo("联机", f"客户端 {addr[0]} 已连接！"))
                # 启动接收线程
                threading.Thread(target=self.recv_net_thread, daemon=True).start()
            except Exception as e:
                self.net_status_var.set("连接失败")
                print(f"服务端错误: {e}")

        # 启动接受连接线程
        threading.Thread(target=accept_thread, daemon=True).start()

    def net_client_connect(self):
        """客户端连接"""
        ip = self.ip_entry.get().strip()
        if not ip:
            messagebox.showwarning("提示", "请输入服务端IP地址")
            return

        if self.net_sock:
            messagebox.showwarning("提示", "已有网络连接，请清空棋局重试！")
            return

        self.net_is_server = False
        self.net_my_color = 1

        try:
            # 创建客户端套接字
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.settimeout(5)
            client.connect((ip, 8899))

            self.net_sock = client
            self.net_running = True
            self.net_status_var.set(f"已连接: {ip}")
            self.game_print.set("成功连接！点击开始游戏")

            # 启动接收线程
            threading.Thread(target=self.recv_net_thread, daemon=True).start()

        except Exception as e:
            messagebox.showerror("连接失败", f"无法连接服务器：{str(e)}")

    def recv_net_thread(self):
        """网络接收循环，使用换行分隔JSON"""
        buffer = b""
        while self.net_running and self.net_sock:
            try:
                data = self.net_sock.recv(4096)
                if not data:
                    break

                buffer += data
                # 按换行分割处理多条消息
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    if line.strip():
                        try:
                            msg = json.loads(line.decode("utf-8"))
                            # 在主线程处理消息
                            self.window.after(0, lambda m=msg: self.handle_net_msg(m))
                        except json.JSONDecodeError:
                            print(f"收到无效JSON: {line}")

            except socket.timeout:
                continue
            except Exception as e:
                print(f"接收异常: {e}")
                break

        # 处理断开连接
        self.window.after(0, self._handle_net_disconnect)

    def _handle_net_disconnect(self):
        """处理断线"""
        if self.net_running:
            self.net_running = False
            self.net_status_var.set("已断开")
            messagebox.showerror("连接断开", "对手已离线或网络中断，棋局重置")
            self.empty_all()

    def handle_net_msg(self, msg):
        """处理网络消息（在主线程执行）"""
        msg_type = msg.get("type")

        if msg_type == "move":
            # 对手落子
            y, x, c = msg["y"], msg["x"], msg["c"]

            # 执行对手落子
            self.do_chess(y, x, c)
            self.last_move = (y, x)
            self._redraw_chessmen()

            # 检查对手是否获胜
            if self.game_win(y, x, c):
                self.game_print.set("对手连成五子，你输了！")
                self._redraw_chessmen()
                return

            # 切换到自己的回合
            self.net_wait = False
            self.game_print.set("轮到你落子！")

        elif msg_type == "win":
            # 对手获胜
            y, x = msg.get("y"), msg.get("x")
            self.do_chess(y, x, 1 - self.net_my_color)
            self.last_move = (y, x)
            self._redraw_chessmen()
            self.game_print.set("对手连成五子，你输了！")
            self.flag_win = 1

        elif msg_type == "giveup":
            # 对手认输
            self.game_print.set("对手认输，你获胜！")
            self.flag_win = 1


if __name__ == "__main__":
    # 设置随机种子，保证AI行为可预测但又有变化
    random.seed(time.time())
    game = Gobang()


'''创作者：wen'''