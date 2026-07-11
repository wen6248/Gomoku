# Creator: wen - Fixed v3.2 - 优化AI大师模式 & 移除思考弹窗 & 顶部退出按钮

import tkinter as tk
from tkinter import messagebox, Tk, Canvas, StringVar, Label, Button, Frame, Entry, IntVar, BooleanVar, Checkbutton, ttk
import tkinter.simpledialog
import tkinter.filedialog
import math
import socket
import threading
import json
import time
import random
import os
from datetime import datetime


# ========================= Scalable Chess Board =========================
class ChessBoard:
    def __init__(self, parent_frame, on_resize_callback):
        self.parent = parent_frame
        self.on_resize = on_resize_callback
        self.canvas = Canvas(parent_frame, bg="#E3C16F", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.cell_size = 30
        self.margin = 25
        self.size = 15
        self.canvas.bind("<Configure>", self._on_configure)
        self.canvas.after(50, self._force_redraw)

    def _on_configure(self, event=None):
        w = self.canvas.winfo_width()
        h = self.canvas.winfo_height()
        if w < 50 or h < 50:
            return
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
        self.canvas.create_rectangle(0, 0, w, h, fill="#E3C16F", outline="", tags="board")
        board_px = self.margin + (self.size - 1) * self.cell_size
        self.canvas.create_rectangle(
            self.margin, self.margin, board_px, board_px,
            outline="#5D4037", width=3, tags="board"
        )
        for i in range(self.size):
            pos = self.margin + i * self.cell_size
            width = 2 if i == 0 or i == self.size - 1 else 1
            self.canvas.create_line(
                self.margin, pos, board_px, pos,
                fill="#3E2723", width=width, tags="board"
            )
            self.canvas.create_line(
                pos, self.margin, pos, board_px,
                fill="#3E2723", width=width, tags="board"
            )
        stars = [(3, 3), (11, 3), (3, 11), (11, 11), (7, 7)]
        r = max(3, self.cell_size * 0.12)
        for sx, sy in stars:
            cx = self.margin + sx * self.cell_size
            cy = self.margin + sy * self.cell_size
            self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r,
                                    fill="#3E2723", outline="", tags="board")

    def get_cell_pos(self, row, col):
        x = self.margin + col * self.cell_size
        y = self.margin + row * self.cell_size
        return x, y

    def get_cell_from_pixel(self, px, py):
        x = (px - self.margin) / self.cell_size
        y = (py - self.margin) / self.cell_size
        col = round(x)
        row = round(y)
        row = max(0, min(self.size - 1, row))
        col = max(0, min(self.size - 1, col))
        return row, col

    def draw_chessman(self, row, col, color, tag="chessman"):
        x, y = self.get_cell_pos(row, col)
        r = max(8, self.cell_size * 0.38)
        shadow_r = r + 1
        shadow_color = "#555555" if color == "white" else "#222222"
        self.canvas.create_oval(
            x - shadow_r + 2, y - shadow_r + 3,
            x + shadow_r + 2, y + shadow_r + 3,
            fill=shadow_color, outline="", tags=tag
        )
        oid = self.canvas.create_oval(
            x - r, y - r, x + r, y + r,
            fill=color, outline="#333" if color == "white" else "#111",
            width=1, tags=tag
        )
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
        x, y = self.get_cell_pos(row, col)
        r = max(3, self.cell_size * 0.12)
        self.canvas.create_oval(
            x - r, y - r, x + r, y + r,
            fill="red", outline="", tags=tag
        )

    def draw_win_line(self, cells, tag="winline"):
        if not cells:
            return
        x1, y1 = self.get_cell_pos(cells[0][0], cells[0][1])
        x2, y2 = self.get_cell_pos(cells[-1][0], cells[-1][1])
        self.canvas.create_line(
            x1, y1, x2, y2,
            fill="#FF5722", width=max(3, self.cell_size * 0.15),
            tags=tag
        )

    def draw_coords(self, tag="coords"):
        self.canvas.delete(tag)
        for i in range(self.size):
            x, y = self.get_cell_pos(0, i)
            label = chr(65 + i)
            self.canvas.create_text(
                x, y - self.cell_size * 0.6,
                text=label, font=("Arial", max(8, int(self.cell_size * 0.3))),
                fill="#5D4037", tags=tag
            )
            x, y = self.get_cell_pos(i, 0)
            self.canvas.create_text(
                x - self.cell_size * 0.6, y,
                text=str(i + 1), font=("Arial", max(8, int(self.cell_size * 0.3))),
                fill="#5D4037", tags=tag
            )


# ========================= Advanced AI Engine (Master Enhanced) =========================
class GobangAI:
    def __init__(self, db, difficulty="medium", callback=None):
        self.db = db
        self.size = 15
        self.difficulty = difficulty
        self.callback = callback
        self.depth_map = {
            "easy": 1,
            "medium": 2,
            "hard": 3,
            "master": 5  # 大师模式深度提升到5
        }
        self.score_map = {
            "five": 10000000,
            "live4": 1000000,
            "dead4": 50000,
            "live3": 80000,
            "sleep3": 8000,
            "live2": 5000,
            "sleep2": 800,
            "one": 100
        }
        self.dirs = [(1, 0), (0, 1), (1, 1), (1, -1)]
        self.opening_book = [
            (7, 7), (7, 6), (6, 7), (8, 7), (7, 8),
            (6, 6), (6, 8), (8, 6), (8, 8),
            (7, 5), (7, 9), (5, 7), (9, 7),
        ]
        self._eval_cache = {}
        self.thinking_steps = 0
        self.killer_moves = {}  # 杀手走法缓存
        self.history_heuristic = {}  # 历史启发

    def _clear_cache(self):
        self._eval_cache.clear()

    def is_empty(self, y, x):
        return 0 <= y < self.size and 0 <= x < self.size and self.db[y][x] == 2

    def is_color(self, y, x, color):
        return 0 <= y < self.size and 0 <= x < self.size and self.db[y][x] == color

    def get_line(self, y, x, dy, dx, color):
        line = []
        cy, cx = y + dy, x + dx
        while 0 <= cy < self.size and 0 <= cx < self.size:
            if self.db[cy][cx] == color:
                line.append(1)
            elif self.db[cy][cx] == 2:
                line.append(0)
                break
            else:
                line.append(-1)
                break
            cy += dy
            cx += dx
        return line

    def analyze_direction(self, y, x, dy, dx, color):
        line1 = self.get_line(y, x, dy, dx, color)
        line2 = self.get_line(y, x, -dy, -dx, color)
        cnt = 1
        for val in line1:
            if val == 1:
                cnt += 1
            else:
                break
        for val in line2:
            if val == 1:
                cnt += 1
            else:
                break
        left_open = len(line2) > 0 and line2[0] == 0
        right_open = len(line1) > 0 and line1[0] == 0
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
        cnt, left_open, right_open, ls, rs = self.analyze_direction(y, x, dy, dx, color)
        if cnt >= 5:
            return self.score_map["five"]
        if cnt == 4:
            if left_open and right_open:
                return self.score_map["live4"]
            elif left_open or right_open:
                return self.score_map["dead4"]
        if cnt == 3:
            if left_open and right_open:
                return self.score_map["live3"]
            elif left_open or right_open:
                return self.score_map["sleep3"]
        if cnt == 2 and left_open and right_open:
            total_space = ls + rs
            if total_space >= 2:
                return self.score_map["live3"] * 0.6
        if cnt == 2:
            if left_open and right_open:
                return self.score_map["live2"]
            elif left_open or right_open:
                return self.score_map["sleep2"]
        if cnt == 1:
            if left_open and right_open:
                return self.score_map["one"] * 2
            elif left_open or right_open:
                return self.score_map["one"]
        return self.score_map["one"] * cnt * 0.3

    def evaluate_point(self, y, x, ai_color, player_color):
        cache_key = (y, x, ai_color, player_color)
        if cache_key in self._eval_cache:
            return self._eval_cache[cache_key]

        if not self.is_empty(y, x):
            return -1

        self.db[y][x] = ai_color
        attack = sum(self.eval_direction(y, x, dy, dx, ai_color) for dy, dx in self.dirs)
        if self.check_win_fast(y, x, ai_color):
            attack += self.score_map["five"] * 10
        self.db[y][x] = player_color
        defense = sum(self.eval_direction(y, x, dy, dx, player_color) for dy, dx in self.dirs)
        if self.check_win_fast(y, x, player_color):
            defense += self.score_map["five"] * 10
        self.db[y][x] = 2

        if self.difficulty == "easy":
            score = attack * 0.4 + defense * 0.6
        elif self.difficulty == "medium":
            score = attack * 0.8 + defense * 1.2
        elif self.difficulty == "hard":
            score = attack * 1.0 + defense * 1.4
        else:  # master
            # 大师模式更注重进攻和防守平衡
            score = attack * 1.3 + defense * 1.7

        self._eval_cache[cache_key] = score
        return score

    def get_candidate_moves(self, radius=2, max_candidates=20):
        candidates = set()
        has_stone = False
        for y in range(self.size):
            for x in range(self.size):
                if self.db[y][x] != 2:
                    has_stone = True
                    for dy in range(-radius, radius + 1):
                        for dx in range(-radius, radius + 1):
                            ny, nx = y + dy, x + dx
                            if self.is_empty(ny, nx):
                                candidates.add((ny, nx))
        if not has_stone:
            return [(7, 7)]

        candidates_list = list(candidates)
        scored = []
        for y, x in candidates_list:
            score = 0
            for dy, dx in self.dirs:
                cnt = 1
                cy, cx = y + dy, x + dx
                while self.is_color(cy, cx, 0) or self.is_color(cy, cx, 1):
                    cnt += 1
                    cy += dy
                    cx += dx
                cy, cx = y - dy, x - dx
                while self.is_color(cy, cx, 0) or self.is_color(cy, cx, 1):
                    cnt += 1
                    cy -= dy
                    cx -= dx
                score += cnt * cnt
            # 添加中心偏好
            center_dist = abs(y - 7) + abs(x - 7)
            score += (14 - center_dist) * 2
            scored.append((score, y, x))

        scored.sort(reverse=True)
        return [(y, x) for _, y, x in scored[:max_candidates]]

    def check_win_fast(self, y, x, color):
        for dy, dx in self.dirs:
            cnt = 1
            cy, cx = y + dy, x + dx
            while self.is_color(cy, cx, color):
                cnt += 1
                cy += dy
                cx += dx
            cy, cx = y - dy, x - dx
            while self.is_color(cy, cx, color):
                cnt += 1
                cy -= dy
                cx -= dx
            if cnt >= 5:
                return True
        return False

    def _get_pattern_score(self, y, x, color):
        """获取更精确的模式评分"""
        score = 0
        for dy, dx in self.dirs:
            # 检查四个方向
            cnt, left_open, right_open, ls, rs = self.analyze_direction(y, x, dy, dx, color)
            if cnt >= 5:
                return self.score_map["five"]
            if cnt == 4:
                if left_open and right_open:
                    score += self.score_map["live4"]
                elif left_open or right_open:
                    score += self.score_map["dead4"]
            elif cnt == 3:
                if left_open and right_open:
                    score += self.score_map["live3"]
                elif left_open or right_open:
                    score += self.score_map["sleep3"]
            elif cnt == 2:
                if left_open and right_open:
                    score += self.score_map["live2"]
                elif left_open or right_open:
                    score += self.score_map["sleep2"]
        return score

    def _minimax(self, depth, alpha, beta, is_maximizing, ai_color, player_color):
        if depth == 0:
            score = 0
            # 更精确的评估
            for y in range(self.size):
                for x in range(self.size):
                    if self.db[y][x] == ai_color:
                        score += self._get_pattern_score(y, x, ai_color) * 0.1
                    elif self.db[y][x] == player_color:
                        score -= self._get_pattern_score(y, x, player_color) * 0.12
            return score

        # 大师模式使用更大的候选集
        if self.difficulty == "master":
            max_candidates = 12 if depth >= 3 else 8
            radius = 2 if depth >= 3 else 1
        else:
            max_candidates = 8 if self.difficulty == "hard" else 6
            radius = 1

        candidates = self.get_candidate_moves(radius=radius, max_candidates=max_candidates)

        if is_maximizing:
            max_eval = -float('inf')
            # 使用杀手走法排序
            candidates.sort(key=lambda pos: self.killer_moves.get(pos, 0), reverse=True)

            for y, x in candidates:
                if not self.is_empty(y, x):
                    continue
                self.db[y][x] = ai_color
                if self.check_win_fast(y, x, ai_color):
                    self.db[y][x] = 2
                    return self.score_map["five"] * (depth + 1)
                eval_score = self._minimax(depth - 1, alpha, beta, False, ai_color, player_color)
                self.db[y][x] = 2
                if eval_score > max_eval:
                    max_eval = eval_score
                    # 更新杀手走法
                    self.killer_moves[(y, x)] = self.killer_moves.get((y, x), 0) + eval_score
                alpha = max(alpha, eval_score)
                if beta <= alpha:
                    break
            return max_eval
        else:
            min_eval = float('inf')
            candidates.sort(key=lambda pos: self.killer_moves.get(pos, 0), reverse=True)

            for y, x in candidates:
                if not self.is_empty(y, x):
                    continue
                self.db[y][x] = player_color
                if self.check_win_fast(y, x, player_color):
                    self.db[y][x] = 2
                    return -self.score_map["five"] * (depth + 1)
                eval_score = self._minimax(depth - 1, alpha, beta, True, ai_color, player_color)
                self.db[y][x] = 2
                if eval_score < min_eval:
                    min_eval = eval_score
                    self.killer_moves[(y, x)] = self.killer_moves.get((y, x), 0) - eval_score
                beta = min(beta, eval_score)
                if beta <= alpha:
                    break
            return min_eval

    def ai_get_pos(self, ai_color, player_color):
        self._clear_cache()
        depth = self.depth_map.get(self.difficulty, 2)

        stone_count = sum(1 for row in self.db for cell in row if cell != 2)
        if stone_count <= 4:
            for pos in self.opening_book:
                if self.is_empty(pos[0], pos[1]):
                    if self.callback:
                        self.callback("AI思考中 - 开局布局...", 0)
                    return pos

        # 大师模式使用更多候选
        if self.difficulty == "master":
            max_candidates = 20
            radius = 2
        else:
            max_candidates = 15 if self.difficulty == "hard" else 10
            radius = 2

        candidates = self.get_candidate_moves(radius=radius, max_candidates=max_candidates)

        if not candidates:
            return 7, 7

        if self.callback:
            self.callback(f"AI深度思考中 (深度{depth})...", 0)

        if depth <= 1:
            best_score = -float('inf')
            best_pos = candidates[0]
            total = len(candidates)
            for i, (y, x) in enumerate(candidates):
                if not self.is_empty(y, x):
                    continue
                if self.callback:
                    self.callback(f"AI评估中... {i + 1}/{total}", int((i + 1) / total * 100))
                score = self.evaluate_point(y, x, ai_color, player_color)
                if score >= self.score_map["five"]:
                    return y, x
                if score > best_score:
                    best_score = score
                    best_pos = (y, x)
            if self.callback:
                self.callback("AI已决定落子位置", 100)
            return best_pos

        best_score = -float('inf')
        best_pos = candidates[0]

        # 更精确的候选评分
        scored_candidates = []
        for y, x in candidates:
            if not self.is_empty(y, x):
                continue
            rough_score = self.evaluate_point(y, x, ai_color, player_color)
            # 大师模式增加更多因素
            if self.difficulty == "master":
                # 考虑中心位置
                center_dist = abs(y - 7) + abs(x - 7)
                rough_score += (14 - center_dist) * 5
                # 考虑周围棋子密度
                density = 0
                for dy in range(-2, 3):
                    for dx in range(-2, 3):
                        if self.is_color(y + dy, x + dx, ai_color) or self.is_color(y + dy, x + dx, player_color):
                            density += 1
                rough_score += density * 2
            scored_candidates.append((rough_score, y, x))

        scored_candidates.sort(reverse=True)
        candidates = [(y, x) for _, y, x in scored_candidates[:max_candidates]]

        # 清空历史启发，为新的搜索做准备
        self.killer_moves = {}

        for i, (y, x) in enumerate(candidates):
            if not self.is_empty(y, x):
                continue
            if self.callback:
                self.callback(f"AI搜索中... {i + 1}/{len(candidates)}", int((i + 1) / len(candidates) * 80))
            self.db[y][x] = ai_color
            if self.check_win_fast(y, x, ai_color):
                self.db[y][x] = 2
                if self.callback:
                    self.callback("AI发现必胜走法！", 100)
                return y, x
            score = self._minimax(depth - 1, -float('inf'), float('inf'), False, ai_color, player_color)
            self.db[y][x] = 2
            if score > best_score:
                best_score = score
                best_pos = (y, x)

        if not self.is_empty(best_pos[0], best_pos[1]):
            for pos in candidates:
                if self.is_empty(pos[0], pos[1]):
                    best_pos = pos
                    break

        if self.callback:
            self.callback("AI已落子", 100)
        return best_pos


# ========================= Main Game Class =========================
class Gobang:
    def __init__(self):
        self.window = Tk()
        self.window.title("五子棋 v3.2 - 智能AI对战 & 局域网联机")
        self.window.geometry("1280x1080")
        self.window.minsize(1000, 820)
        self.window.configure(bg="#F5F5DC")

        self.db = [[2] * 15 for _ in range(15)]
        self.order = []
        self.color_count = 0
        self.color = 'black'
        self.flag_win = 1
        self.flag_empty = 1
        self.last_move = None
        self.win_line_cells = []
        self.move_history = []
        self.step_count = 0
        self.black_time = 0
        self.white_time = 0
        self.timer_running = False
        self.ai_thinking = False
        self.ai_progress = 0

        self.game_mode = StringVar(value="local")
        self.ai_difficulty = StringVar(value="medium")
        self.show_coords = BooleanVar(value=False)
        self.show_hints = BooleanVar(value=True)
        self.show_last_move = BooleanVar(value=True)
        self.net_sock = None
        self.net_is_server = False
        self.net_running = False
        self.net_my_color = 0
        self.net_wait = False
        self.net_peer_name = ""

        self.ai = GobangAI(self.db, difficulty=self.ai_difficulty.get(), callback=self._on_ai_thinking)

        self._build_ui()
        self.board.canvas.bind("<Button-1>", self.chess_moving)
        self.board.canvas.bind("<Motion>", self.on_mouse_move)
        self.window.mainloop()

    def _on_ai_thinking(self, text, progress):
        """AI思考回调 - 更新状态栏而不是弹窗"""
        self.ai_progress = progress
        if progress >= 100:
            self.game_print.set(f"✅ AI已落子")
            self.ai_thinking = False
        else:
            self.game_print.set(f"🤖 {text}")
        self.window.update_idletasks()

    def _build_ui(self):
        # 主框架
        main_frame = Frame(self.window, bg="#F5F5DC")
        main_frame.pack(fill="both", expand=True, padx=5, pady=8)

        # 顶部工具栏 - 包含退出按钮
        top_bar = Frame(main_frame, bg="#5D4037", height=40)
        top_bar.pack(fill="x", pady=(0, 5))
        top_bar.pack_propagate(False)

        # 左对齐标题
        Label(top_bar, text="♟ 五子棋 v3.2", font=("Microsoft YaHei", 14, "bold"),
              bg="#5D4037", fg="#FFE0B2").pack(side="left", padx=15)

        # 右对齐退出按钮
        quit_btn = Button(top_bar, text="✖ 退出", command=self.window.destroy,
                          font=("Microsoft YaHei", 10, "bold"), bg="#D32F2F",
                          fg="white", bd=0, cursor="hand2", padx=15, pady=5)
        quit_btn.pack(side="right", padx=10)

        # 主体布局
        body_frame = Frame(main_frame, bg="#F5F5DC")
        body_frame.pack(fill="both", expand=True)

        board_frame = Frame(body_frame, bg="#8D6E63", bd=3, relief="ridge")
        board_frame.pack(side="left", fill="both", expand=True, padx=5, pady=8)
        self.board = ChessBoard(board_frame, on_resize_callback=self._redraw_chessmen)

        # 右侧控制面板
        ctrl_frame = Frame(body_frame, bg="#FFF8E1", width=360, bd=3, relief="groove")
        ctrl_frame.pack(side="right", fill="y", padx=5, pady=8)
        ctrl_frame.pack_propagate(False)

        # 创建滚动容器
        canvas = Canvas(ctrl_frame, bg="#FFF8E1", highlightthickness=0)
        scrollbar = tk.Scrollbar(ctrl_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = Frame(canvas, bg="#FFF8E1")

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self._build_scrollable_content(scrollable_frame)
        self._update_timer()

    def _build_scrollable_content(self, parent):
        """构建可滚动面板内容"""

        # 状态卡片
        status_frame = Frame(parent, bg="#FFF3E0", bd=2, relief="flat", padx=10, pady=8)
        status_frame.pack(fill="x", padx=10, pady=4)

        self.game_print = StringVar(value="请选择模式并开始")
        self.status_label = Label(status_frame, textvariable=self.game_print,
                                  font=("Microsoft YaHei", 11, "bold"), bg="#FFF3E0",
                                  fg="#D84315", wraplength=320)
        self.status_label.pack()

        # AI进度条（只在大师模式显示）
        self.ai_progress_frame = Frame(parent, bg="#FFF8E1")
        self.ai_progress_frame.pack(fill="x", padx=10, pady=2)
        self.ai_progress_bar = ttk.Progressbar(self.ai_progress_frame, length=300,
                                               mode='determinate', value=0)
        self.ai_progress_bar.pack(fill="x")
        self.ai_progress_frame.pack_forget()  # 默认隐藏

        # 信息卡片
        info_frame = Frame(parent, bg="#FFFFFF", bd=1, relief="solid", padx=12, pady=8)
        info_frame.pack(pady=4, fill="x", padx=10)

        row1 = Frame(info_frame, bg="#FFFFFF")
        row1.pack(fill="x", pady=2)
        Label(row1, text="⏱ 对局时间:", font=("Microsoft YaHei", 10),
              bg="#FFFFFF", fg="#5D4037").pack(side="left")
        self.timer_var = StringVar(value="00:00")
        Label(row1, textvariable=self.timer_var, font=("Microsoft YaHei", 14, "bold"),
              bg="#FFFFFF", fg="#E65100").pack(side="left", padx=5)

        Label(row1, text="  步数:", font=("Microsoft YaHei", 10),
              bg="#FFFFFF", fg="#5D4037").pack(side="left", padx=(15, 0))
        self.step_var = StringVar(value="0")
        Label(row1, textvariable=self.step_var, font=("Microsoft YaHei", 14, "bold"),
              bg="#FFFFFF", fg="#E65100").pack(side="left", padx=5)

        row2 = Frame(info_frame, bg="#FFFFFF")
        row2.pack(fill="x", pady=2)
        Label(row2, text="🎯 当前落子:", font=("Microsoft YaHei", 10),
              bg="#FFFFFF", fg="#5D4037").pack(side="left")
        self.turn_var = StringVar(value="未开始")
        self.turn_label = Label(row2, textvariable=self.turn_var,
                                font=("Microsoft YaHei", 11, "bold"),
                                bg="#FFFFFF", fg="#333")
        self.turn_label.pack(side="left", padx=5)

        # 分隔线
        Frame(parent, bg="#D7CCC8", height=2).pack(fill="x", pady=6, padx=10)

        # 模式选择
        mode_card = Frame(parent, bg="#E8F5E9", bd=1, relief="solid", padx=10, pady=8)
        mode_card.pack(pady=4, fill="x", padx=10)
        Label(mode_card, text="🎮 游戏模式", font=("Microsoft YaHei", 11, "bold"),
              bg="#E8F5E9", fg="#2E7D32").pack(anchor="w")

        mode_btn_frame = Frame(mode_card, bg="#E8F5E9")
        mode_btn_frame.pack(fill="x", pady=4)

        modes = [
            ("👥 双人", "local", "#4CAF50"),
            ("🤖 人机", "ai", "#2196F3"),
            ("🌐 局域网", "net", "#FF9800")
        ]
        for i, (text, val, color) in enumerate(modes):
            rb = tk.Radiobutton(mode_btn_frame, text=text, variable=self.game_mode,
                                value=val, font=("Microsoft YaHei", 10),
                                bg="#E8F5E9", activebackground="#E8F5E9",
                                selectcolor=color, command=self._on_mode_change)
            rb.grid(row=0, column=i, padx=5, pady=2, sticky="w")

        # AI设置卡片
        self.ai_card = Frame(parent, bg="#FFF3E0", bd=1, relief="solid", padx=10, pady=8)
        self.ai_card.pack(pady=4, fill="x", padx=10)
        self.ai_card_visible = True
        Label(self.ai_card, text="🧠 AI难度", font=("Microsoft YaHei", 11, "bold"),
              bg="#FFF3E0", fg="#E65100").pack(anchor="w")

        ai_btn_frame = Frame(self.ai_card, bg="#FFF3E0")
        ai_btn_frame.pack(fill="x", pady=4)

        ai_levels = [("🟢 简单", "easy"), ("🟡 中等", "medium"),
                     ("🟠 困难", "hard"), ("🔴 大师", "master")]
        for i, (text, val) in enumerate(ai_levels):
            rb = tk.Radiobutton(ai_btn_frame, text=text, variable=self.ai_difficulty,
                                value=val, font=("Microsoft YaHei", 9),
                                bg="#FFF3E0", activebackground="#FFF3E0",
                                selectcolor="#FF9800",
                                command=self._on_difficulty_change)
            rb.grid(row=0, column=i, padx=2, pady=1, sticky="w")

        # 网络设置卡片
        self.net_card = Frame(parent, bg="#E3F2FD", bd=1, relief="solid", padx=10, pady=8)
        self.net_card.pack(pady=4, fill="x", padx=10)
        self.net_card_visible = True
        self._build_net_ui()
        self.net_card.pack_forget()
        self.net_card_visible = False

        # 分隔线
        Frame(parent, bg="#D7CCC8", height=2).pack(fill="x", pady=6, padx=10)

        # 设置选项
        settings_card = Frame(parent, bg="#F3E5F5", bd=1, relief="solid", padx=10, pady=8)
        settings_card.pack(pady=4, fill="x", padx=10)
        Label(settings_card, text="⚙️ 显示设置", font=("Microsoft YaHei", 11, "bold"),
              bg="#F3E5F5", fg="#6A1B9A").pack(anchor="w")

        settings_btn_frame = Frame(settings_card, bg="#F3E5F5")
        settings_btn_frame.pack(fill="x", pady=4)
        Checkbutton(settings_btn_frame, text="📌 显示坐标", variable=self.show_coords,
                    bg="#F3E5F5", font=("Microsoft YaHei", 10),
                    command=self._toggle_coords).grid(row=0, column=0, sticky="w")
        Checkbutton(settings_btn_frame, text="💡 落子提示", variable=self.show_hints,
                    bg="#F3E5F5", font=("Microsoft YaHei", 10),
                    command=self._toggle_hints).grid(row=0, column=1, sticky="w", padx=10)
        Checkbutton(settings_btn_frame, text="📍 末手标记", variable=self.show_last_move,
                    bg="#F3E5F5", font=("Microsoft YaHei", 10),
                    command=self._redraw_chessmen).grid(row=1, column=0, sticky="w", pady=(4, 0))

        # 分隔线
        Frame(parent, bg="#D7CCC8", height=2).pack(fill="x", pady=6, padx=10)

        # 操作按钮
        btn_card = Frame(parent, bg="#FFFFFF", bd=1, relief="solid", padx=10, pady=8)
        btn_card.pack(pady=4, fill="x", padx=10)

        btn_style = {
            "font": ("Microsoft YaHei", 10, "bold"),
            "width": 13,
            "fg": "white",
            "activeforeground": "white",
            "bd": 0,
            "cursor": "hand2",
            "pady": 4,
            "relief": "flat"
        }

        buttons = [
            ("▶ 开始游戏", self.game_start, "#4CAF50"),
            ("↩ 悔棋", self.withdraw, "#FF9800"),
            ("⏸ 停走一步", self.take_a_stop, "#2196F3"),
            ("💾 保存棋局", self.save_game, "#9C27B0"),
            ("📂 加载棋局", self.load_game, "#009688"),
            ("🗑 清空棋局", self.empty_all, "#795548"),
            ("🏳 认输", self.ren_shu, "#F44336"),
            ("📖 游戏规则", self.rules_of_the_game, "#455A64"),
        ]

        for i, (text, cmd, color) in enumerate(buttons):
            row = i // 2
            col = i % 2
            style = btn_style.copy()
            style["bg"] = color
            btn = Button(btn_card, text=text, command=cmd, **style)
            btn.grid(row=row, column=col, padx=3, pady=3, sticky="ew")
            btn.bind("<Enter>", lambda e, b=btn, c=color: b.configure(bg=self._lighten_color(c)))
            btn.bind("<Leave>", lambda e, b=btn, c=color: b.configure(bg=c))

        btn_card.grid_columnconfigure(0, weight=1)
        btn_card.grid_columnconfigure(1, weight=1)

        # 底部版本信息
        Label(parent, text="v3.2 | 大师模式增强 | 纯离线运行",
              font=("Arial", 9), bg="#FFF8E1", fg="#9E9E9E").pack(side="bottom", pady=8)

    def _lighten_color(self, color):
        colors = {
            "#4CAF50": "#66BB6A",
            "#FF9800": "#FFA726",
            "#2196F3": "#42A5F5",
            "#9C27B0": "#AB47BC",
            "#009688": "#26A69A",
            "#795548": "#8D6E63",
            "#F44336": "#EF5350",
            "#455A64": "#546E7A",
        }
        return colors.get(color, color)

    def _build_net_ui(self):
        for w in self.net_card.winfo_children():
            w.destroy()
        Label(self.net_card, text="🌐 联机设置", font=("Microsoft YaHei", 11, "bold"),
              bg="#E3F2FD", fg="#0D47A1").pack(anchor="w")

        self.local_ip_var = StringVar(value="IP: 获取中...")
        Label(self.net_card, textvariable=self.local_ip_var, font=("Arial", 9),
              bg="#E3F2FD", fg="#333").pack(anchor="w")
        self._update_local_ip()

        net_btn_frame = Frame(self.net_card, bg="#E3F2FD")
        net_btn_frame.pack(pady=4, fill="x")

        Button(net_btn_frame, text="🔌 开启服务端", command=self.net_server_start,
               font=("Microsoft YaHei", 10, "bold"), bg="#43A047", fg="white", bd=0,
               cursor="hand2", padx=10, pady=3).pack(side="left", padx=2)

        conn_frame = Frame(net_btn_frame, bg="#E3F2FD")
        conn_frame.pack(side="left", padx=5)
        Label(conn_frame, text="IP:", font=("Arial", 9), bg="#E3F2FD").pack(side="left")
        self.ip_entry = Entry(conn_frame, font=("Arial", 9), width=12,
                              justify="center", bd=1, relief="solid")
        self.ip_entry.pack(side="left", padx=2)
        self.ip_entry.insert(0, "127.0.0.1")
        Button(conn_frame, text="连接", command=self.net_client_connect,
               font=("Microsoft YaHei", 10, "bold"), bg="#1E88E5", fg="white", bd=0,
               cursor="hand2", padx=8, pady=3).pack(side="left", padx=2)

        self.net_status_var = StringVar(value="⚪ 连接断开")
        Label(self.net_card, textvariable=self.net_status_var, font=("Arial", 9),
              bg="#E3F2FD", fg="#666").pack(pady=4)

    def _update_local_ip(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
        except:
            ip = "无法获取"
        self.local_ip_var.set(f"📶 本机IP: {ip}")

    def _on_mode_change(self):
        mode = self.game_mode.get()
        if mode == "net":
            if not self.net_card_visible:
                self.net_card.pack(pady=4, fill="x", padx=10, after=self.ai_card)
                self.net_card_visible = True
            self.ai_card.pack_forget()
            self.ai_card_visible = False
        elif mode == "ai":
            if not self.ai_card_visible:
                self.ai_card.pack(pady=4, fill="x", padx=10, before=self.net_card)
                self.ai_card_visible = True
            if self.net_card_visible:
                self.net_card.pack_forget()
                self.net_card_visible = False
        else:
            if not self.ai_card_visible:
                self.ai_card.pack(pady=4, fill="x", padx=10, before=self.net_card)
                self.ai_card_visible = True
            if self.net_card_visible:
                self.net_card.pack_forget()
                self.net_card_visible = False

    def _on_difficulty_change(self):
        self.ai.difficulty = self.ai_difficulty.get()
        self.ai.depth_map = {
            "easy": 1,
            "medium": 2,
            "hard": 3,
            "master": 5
        }
        # 显示/隐藏进度条（仅大师模式显示）
        if self.ai_difficulty.get() == "master":
            self.ai_progress_frame.pack(fill="x", padx=10, pady=2)
        else:
            self.ai_progress_frame.pack_forget()
        self.game_print.set(f"AI难度已切换为: {self._difficulty_name()}")

    def _difficulty_name(self):
        names = {"easy": "简单", "medium": "中等", "hard": "困难", "master": "大师"}
        return names.get(self.ai_difficulty.get(), "中等")

    def _toggle_coords(self):
        if self.show_coords.get():
            self.board.draw_coords()
        else:
            self.board.canvas.delete("coords")

    def _toggle_hints(self):
        if not self.show_hints.get():
            self.board.canvas.delete("hint")
            self.board.canvas.delete("hint_hover")

    def on_mouse_move(self, event):
        if not self.show_hints.get() or self.flag_win == 1 or self.flag_empty == 0 or self.ai_thinking:
            self.board.canvas.delete("hint_hover")
            return
        row, col = self.board.get_cell_from_pixel(event.x, event.y)
        if self.limit_boarder(row, col) and self.db[row][col] == 2:
            self.board.canvas.delete("hint_hover")
            x, y = self.board.get_cell_pos(row, col)
            r = max(4, self.board.cell_size * 0.18)
            color = "#444444" if self.color == "black" else "#CCCCCC"
            self.board.canvas.create_oval(
                x - r, y - r, x + r, y + r,
                fill=color, outline="#FFD700", width=2,
                tags="hint_hover", stipple="gray50"
            )
        else:
            self.board.canvas.delete("hint_hover")

    def _update_timer(self):
        if self.timer_running and self.flag_win == 0:
            self.black_time += 1 if self.color_count == 0 else 0
            self.white_time += 1 if self.color_count == 1 else 0
            total = self.black_time + self.white_time
            mins = total // 60
            secs = total % 60
            self.timer_var.set(f"{mins:02d}:{secs:02d}")
        self.window.after(1000, self._update_timer)

    def _update_turn_display(self):
        if self.flag_win == 1:
            self.turn_var.set("🏁 游戏结束")
            self.turn_label.config(fg="#9E9E9E")
        elif self.flag_empty == 0:
            self.turn_var.set("⏸ 未开始")
            self.turn_label.config(fg="#9E9E9E")
        elif self.ai_thinking:
            self.turn_var.set("🤖 AI思考中...")
            self.turn_label.config(fg="#FF6F00")
        else:
            mode = self.game_mode.get()
            if mode == "ai":
                if self.color_count == 0:
                    self.turn_var.set("👤 玩家(黑)")
                    self.turn_label.config(fg="black")
                else:
                    self.turn_var.set("🤖 AI(白)")
                    self.turn_label.config(fg="#666666")
            elif mode == "net":
                my_color_name = "黑棋" if self.net_my_color == 0 else "白棋"
                if self.net_wait:
                    self.turn_var.set(f"⏳ 等待对手...")
                    self.turn_label.config(fg="#FF9800")
                else:
                    self.turn_var.set(f"🎯 轮到你 ({my_color_name})")
                    self.turn_label.config(fg="black" if self.net_my_color == 0 else "#666666")
            else:
                color_emoji = "⚫" if self.color == "black" else "⚪"
                self.turn_var.set(f"{color_emoji} {self.color}")
                self.turn_label.config(fg="black" if self.color == "black" else "#666666")

    def _redraw_chessmen(self):
        self.board.canvas.delete("chessman")
        self.board.canvas.delete("marker")
        self.board.canvas.delete("winline")
        self.board.paint_board()

        for idx in self.order:
            x = idx % 15
            y = idx // 15
            color_idx = self.db[y][x]
            fill_c = "black" if color_idx == 0 else "white"
            self.board.draw_chessman(y, x, fill_c)

        if self.show_last_move.get() and self.last_move and self.flag_win == 0:
            ly, lx = self.last_move
            self.board.draw_last_move_marker(ly, lx)

        if self.win_line_cells and self.flag_win == 1:
            self.board.draw_win_line(self.win_line_cells)

        if self.show_coords.get():
            self.board.draw_coords()

    def change_color(self):
        self.color_count = (self.color_count + 1) % 2
        self.color = "black" if self.color_count == 0 else "white"
        self._update_turn_display()

    def limit_boarder(self, y, x):
        return 0 <= x <= 14 and 0 <= y <= 14

    def chessman_count(self, y, x, color_count):
        counts = []
        lines = []
        for dy, dx in [(0, 1), (1, 0), (1, 1), (1, -1)]:
            cells = [(y, x)]
            cnt = 1
            cy, cx = y + dy, x + dx
            while self.limit_boarder(cy, cx) and self.db[cy][cx] == color_count:
                cnt += 1
                cells.append((cy, cx))
                cy += dy
                cx += dx
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
        if self.chessman_count(y, x, color_count) >= 5:
            self.flag_win = 1
            self.flag_empty = 0
            self.timer_running = False
            return True
        return False

    def withdraw(self):
        if self.ai_thinking:
            return
        if len(self.order) == 0 or self.flag_win == 1:
            if self.game_mode.get() == "net":
                messagebox.showwarning("提示", "联机模式无法悔棋！")
            return

        steps = 2 if self.game_mode.get() == "ai" and len(self.order) >= 2 else 1

        for _ in range(steps):
            if not self.order:
                break
            z = self.order.pop()
            x = z % 15
            y = z // 15
            self.db[y][x] = 2
            if self.move_history:
                self.move_history.pop()

        self.step_count = len(self.order)
        self.step_var.set(str(self.step_count))

        self.color_count = 0 if self.step_count % 2 == 0 else 1
        self.color = "black" if self.color_count == 0 else "white"
        self.last_move = None
        self.win_line_cells = []
        self.flag_win = 1
        self.flag_empty = 1
        self.timer_running = False
        self._redraw_chessmen()
        self._update_turn_display()
        self.game_print.set("↩ 已悔棋，请点击开始游戏继续")

    def empty_all(self):
        self.ai_thinking = False
        self.ai_progress = 0

        if self.net_sock:
            self.net_running = False
            try:
                self.net_sock.close()
            except:
                pass
            self.net_sock = None
        self.net_status_var.set("⚪ 连接断开")

        self.board.canvas.delete("chessman")
        self.board.canvas.delete("marker")
        self.board.canvas.delete("winline")
        self.board.canvas.delete("hint")
        self.board.canvas.delete("hint_hover")

        self.db = [[2] * 15 for _ in range(15)]
        self.order = []
        self.color_count = 0
        self.color = "black"
        self.flag_win = 1
        self.flag_empty = 1
        self.last_move = None
        self.win_line_cells = []
        self.net_wait = False
        self.move_history = []
        self.step_count = 0
        self.step_var.set("0")
        self.timer_running = False
        self.black_time = 0
        self.white_time = 0
        self.timer_var.set("00:00")
        self._update_turn_display()
        self.game_print.set("🗑 棋局已清空")
        self.ai_progress_bar['value'] = 0

    def save_game(self):
        if len(self.order) == 0:
            messagebox.showinfo("提示", "棋局为空，无需保存")
            return
        try:
            filename = tk.filedialog.asksaveasfilename(
                defaultextension=".gobang",
                filetypes=[("Gobang Save", "*.gobang"), ("All Files", "*.*")],
                title="保存棋局"
            )
            if not filename:
                return
            data = {
                "version": "3.2",
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "mode": self.game_mode.get(),
                "db": self.db,
                "order": self.order,
                "color_count": self.color_count,
                "flag_win": self.flag_win,
                "flag_empty": self.flag_empty,
                "last_move": self.last_move,
                "win_line_cells": self.win_line_cells,
                "move_history": self.move_history,
                "step_count": self.step_count,
                "timer": self.timer_var.get()
            }
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            messagebox.showinfo("保存成功", f"💾 棋局已保存到:\n{filename}")
        except Exception as e:
            messagebox.showerror("保存失败", f"错误: {str(e)}")

    def load_game(self):
        try:
            filename = tk.filedialog.askopenfilename(
                filetypes=[("Gobang Save", "*.gobang"), ("All Files", "*.*")],
                title="加载棋局"
            )
            if not filename:
                return
            with open(filename, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.db = data.get("db", [[2] * 15 for _ in range(15)])
            self.order = data.get("order", [])
            self.color_count = data.get("color_count", 0)
            self.color = "black" if self.color_count == 0 else "white"
            self.flag_win = data.get("flag_win", 1)
            self.flag_empty = data.get("flag_empty", 1)
            self.last_move = data.get("last_move")
            self.win_line_cells = data.get("win_line_cells", [])
            self.move_history = data.get("move_history", [])
            self.step_count = data.get("step_count", len(self.order))
            self.step_var.set(str(self.step_count))

            self.ai = GobangAI(self.db, difficulty=self.ai_difficulty.get(), callback=self._on_ai_thinking)

            self._redraw_chessmen()
            self._update_turn_display()

            if self.flag_win == 1 and self.flag_empty == 0:
                self.game_print.set("📂 已加载已结束的棋局")
            elif self.flag_win == 0:
                self.game_print.set("📂 已加载棋局，点击开始游戏继续")
                self.timer_running = True
            else:
                self.game_print.set("📂 已加载棋局")

            messagebox.showinfo("加载成功", f"📂 棋局已加载:\n{filename}")
        except Exception as e:
            messagebox.showerror("加载失败", f"错误: {str(e)}")

    def rules_of_the_game(self):
        msg = (
            "📖 游戏规则 v3.2:\n\n"
            "👥 双人本地: 黑棋先行，轮流落子\n\n"
            "🤖 人机对战: 玩家执黑，AI执白\n"
            "   🟢 简单: AI随机性较大，适合新手\n"
            "   🟡 中等: 标准AI水平，有一定挑战\n"
            "   🟠 困难: 深度搜索，实力较强\n"
            "   🔴 大师: 深度5层搜索+杀手走法，极具挑战\n\n"
            "🌐 局域网联机: \n"
            "   一方开启服务端，另一方连接\n"
            "   服务端执黑，客户端执白\n\n"
            "🏆 先连成五子的一方获胜\n"
            "🔄 窗口可缩放，棋盘自适应\n"
            "💾 支持保存/加载棋局、悔棋、认输\n"
            "💡 可开启坐标显示和落子提示\n"
            "⚡ 大师模式使用增强算法，纯离线运行"
        )
        messagebox.showinfo("游戏规则", msg)

    def take_a_stop(self):
        if self.flag_win == 1 or self.game_mode.get() == "net" or self.ai_thinking:
            return
        self.change_color()
        self.game_print.set(f"⏸ {self.color} 回合")

    def game_start(self):
        if self.flag_empty == 0:
            return

        self.ai_thinking = False
        self.ai_progress = 0
        self.ai_progress_bar['value'] = 0

        self.flag_win = 0
        self.color_count = 0
        self.color = "black"
        self.win_line_cells = []
        self.last_move = None
        self.step_count = 0
        self.step_var.set("0")
        self.move_history = []
        self.black_time = 0
        self.white_time = 0
        self.timer_running = True
        self._redraw_chessmen()
        self._update_turn_display()

        # 大师模式显示进度条
        if self.ai_difficulty.get() == "master":
            self.ai_progress_frame.pack(fill="x", padx=10, pady=2)
        else:
            self.ai_progress_frame.pack_forget()

        mode = self.game_mode.get()
        if mode == "ai":
            self.ai = GobangAI(self.db, difficulty=self.ai_difficulty.get(), callback=self._on_ai_thinking)
            self.game_print.set(f"🤖 你执黑先行 [AI难度: {self._difficulty_name()}]")
        elif mode == "net":
            if not self.net_sock:
                messagebox.showwarning("提示", "请先建立联机连接！")
                self.flag_win = 1
                self.flag_empty = 1
                self.timer_running = False
                return
            if self.net_is_server:
                self.net_my_color = 0
                self.net_wait = False
                self.color_count = 0
                self.color = "black"
                self.game_print.set("🌐 你是黑棋，请落子")
            else:
                self.net_my_color = 1
                self.net_wait = True
                self.color_count = 1
                self.color = "white"
                self.game_print.set("🌐 你是白棋，等待黑方落子...")
            self._update_turn_display()
        else:
            self.game_print.set("👥 请黑方落子")

    def ren_shu(self):
        if self.flag_win == 1 or self.ai_thinking:
            return
        winner = "白棋" if self.color == "black" else "黑棋"
        self.game_print.set(f"🏳 {winner} 获胜 (认输)")
        self.flag_win = 1
        self.flag_empty = 0
        self.timer_running = False
        self._update_turn_display()
        if self.game_mode.get() == "net" and self.net_sock:
            self._net_send({"type": "giveup"})

    def chess_moving(self, event):
        if self.flag_win == 1 or self.flag_empty == 0 or self.ai_thinking:
            return

        mode = self.game_mode.get()

        if mode == "net" and self.net_wait:
            messagebox.showinfo("等待", "⏳ 现在不是你的落子回合！")
            return

        row, col = self.board.get_cell_from_pixel(event.x, event.y)

        if not self.limit_boarder(row, col) or self.db[row][col] != 2:
            return

        if mode == "net":
            color_idx = self.net_my_color
        else:
            color_idx = self.color_count

        self.do_chess(row, col, color_idx)
        self.last_move = (row, col)
        self.step_count += 1
        self.step_var.set(str(self.step_count))
        self.move_history.append({
            "step": self.step_count,
            "player": "黑棋" if color_idx == 0 else "白棋",
            "pos": f"{chr(65 + col)}{row + 1}",
            "row": row, "col": col
        })
        self._redraw_chessmen()

        if self.game_win(row, col, color_idx):
            winner = "黑棋" if color_idx == 0 else "白棋"
            self.game_print.set(f"🎉 {winner} 获胜！")
            self._redraw_chessmen()
            self._update_turn_display()
            if mode == "net":
                self._net_send({"type": "win", "y": row, "x": col, "c": color_idx})
            return

        if mode == "ai":
            self.change_color()
            self.ai_thinking = True
            self._update_turn_display()
            self.game_print.set("🤖 AI思考中...")

            # 在后台线程中运行AI
            def ai_thread():
                try:
                    ai_y, ai_x = self.ai.ai_get_pos(ai_color=1, player_color=0)
                    self.window.after(0, lambda: self._ai_move_result(ai_y, ai_x))
                except Exception as e:
                    self.window.after(0, lambda: self._ai_error(str(e)))

            threading.Thread(target=ai_thread, daemon=True).start()

        elif mode == "net":
            self.net_wait = True
            self._update_turn_display()
            self.game_print.set("⏳ 等待对手落子...")
            self._net_send({"type": "move", "y": row, "x": col, "c": color_idx})

        else:
            self.change_color()
            self.game_print.set(f"{self.color} 回合")

    def _ai_move_result(self, ai_y, ai_x):
        """AI落子结果"""
        self.ai_thinking = False
        self.ai_progress_bar['value'] = 100

        if self.db[ai_y][ai_x] == 2:
            self.do_chess(ai_y, ai_x, 1)
            self.last_move = (ai_y, ai_x)
            self.step_count += 1
            self.step_var.set(str(self.step_count))
            self.move_history.append({
                "step": self.step_count,
                "player": "AI(白)",
                "pos": f"{chr(65 + ai_x)}{ai_y + 1}",
                "row": ai_y, "col": ai_x
            })
            self._redraw_chessmen()

            if self.game_win(ai_y, ai_x, 1):
                self.game_print.set("🤖 AI(白棋) 获胜！")
                self._redraw_chessmen()
                self._update_turn_display()
                return

        self.change_color()
        self.game_print.set("👤 请你(黑棋)落子")
        self._update_turn_display()

    def _ai_error(self, error_msg):
        """AI错误处理"""
        self.ai_thinking = False
        messagebox.showerror("AI错误", f"AI思考出错: {error_msg}")
        self.game_print.set("⚠️ AI出错，请重新开始")

    def do_chess(self, y, x, color_idx):
        if self.db[y][x] == 2:
            self.db[y][x] = color_idx
            self.order.append(x + 15 * y)

    def _net_send(self, data):
        if not self.net_sock:
            return
        try:
            msg = json.dumps(data, ensure_ascii=False) + "\n"
            self.net_sock.send(msg.encode("utf-8"))
        except Exception as e:
            print(f"发送失败: {e}")
            self.window.after(0, lambda: self._handle_net_disconnect())

    def net_server_start(self):
        if self.net_sock:
            messagebox.showwarning("提示", "已有网络连接，请清空棋局重试！")
            return

        self.net_is_server = True
        self.net_my_color = 0

        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            server.bind(("0.0.0.0", 8899))
        except Exception as e:
            messagebox.showerror("错误", f"端口被占用: {e}")
            return

        server.listen(1)
        self.net_status_var.set("⏳ 等待对手...")
        self.game_print.set("🔌 服务端已开启，等待客户端...")

        def accept_thread():
            try:
                conn, addr = server.accept()
                self.net_sock = conn
                self.net_running = True
                self.net_status_var.set(f"✅ 已连接: {addr[0]}")
                self.game_print.set("🌐 客户端已连接！点击开始游戏")
                self.window.after(0, lambda: messagebox.showinfo("联机", f"✅ 客户端 {addr[0]} 已连接！"))
                threading.Thread(target=self.recv_net_thread, daemon=True).start()
            except Exception as e:
                self.net_status_var.set("❌ 连接失败")
                print(f"服务端错误: {e}")

        threading.Thread(target=accept_thread, daemon=True).start()

    def net_client_connect(self):
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
            client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client.settimeout(5)
            client.connect((ip, 8899))

            self.net_sock = client
            self.net_running = True
            self.net_status_var.set(f"✅ 已连接: {ip}")
            self.game_print.set("🌐 成功连接！点击开始游戏")

            threading.Thread(target=self.recv_net_thread, daemon=True).start()

        except Exception as e:
            messagebox.showerror("连接失败", f"无法连接服务器：{str(e)}")

    def recv_net_thread(self):
        buffer = b""
        while self.net_running and self.net_sock:
            try:
                data = self.net_sock.recv(4096)
                if not data:
                    break

                buffer += data
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    if line.strip():
                        try:
                            msg = json.loads(line.decode("utf-8"))
                            self.window.after(0, lambda m=msg: self.handle_net_msg(m))
                        except json.JSONDecodeError:
                            print(f"收到无效JSON: {line}")

            except socket.timeout:
                continue
            except Exception as e:
                print(f"接收异常: {e}")
                break

        self.window.after(0, self._handle_net_disconnect)

    def _handle_net_disconnect(self):
        if self.net_running:
            self.net_running = False
            self.net_status_var.set("❌ 连接断开")
            messagebox.showerror("连接断开", "对手已离线或网络中断，棋局重置")
            self.empty_all()

    def handle_net_msg(self, msg):
        msg_type = msg.get("type")

        if msg_type == "move":
            y, x, c = msg["y"], msg["x"], msg["c"]

            expected_opponent_color = 1 - self.net_my_color
            if c != expected_opponent_color:
                print(f"警告: 收到异常颜色 {c}, expected {expected_opponent_color}")
                c = expected_opponent_color

            self.do_chess(y, x, c)
            self.last_move = (y, x)
            self.step_count += 1
            self.step_var.set(str(self.step_count))
            self.move_history.append({
                "step": self.step_count,
                "player": "对手",
                "pos": f"{chr(65 + x)}{y + 1}",
                "row": y, "col": x
            })
            self._redraw_chessmen()

            if self.game_win(y, x, c):
                winner = "黑棋" if c == 0 else "白棋"
                self.game_print.set(f"🎉 {winner} wins, you lose!")
                self._redraw_chessmen()
                self._update_turn_display()
                return

            self.net_wait = False
            self._update_turn_display()
            self.game_print.set("🎯 轮到你落子！")

        elif msg_type == "win":
            y, x, c = msg.get("y"), msg.get("x"), msg.get("c", 1 - self.net_my_color)
            expected_opponent_color = 1 - self.net_my_color
            if c != expected_opponent_color:
                c = expected_opponent_color
            self.do_chess(y, x, c)
            self.last_move = (y, x)
            self._redraw_chessmen()
            winner = "黑棋" if c == 0 else "白棋"
            self.game_print.set(f"🎉 {winner} wins, you lose!")
            self.flag_win = 1
            self._update_turn_display()

        elif msg_type == "giveup":
            self.game_print.set("🏳 对手认输，你获胜！")
            self.flag_win = 1
            self._update_turn_display()


if __name__ == "__main__":
    random.seed(time.time())
    game = Gobang()