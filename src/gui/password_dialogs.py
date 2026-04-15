"""
密码输入对话框
支持字节级十六进制输入（00-FF）
"""

import tkinter as tk
from tkinter import ttk, messagebox
from src.core.types import CardType
from src.core.constants import IC_OK


class PasswordDialog(tk.Toplevel):
    def __init__(self, parent, card_type: CardType, remaining_attempts: int = -1):
        super().__init__(parent)
        self.result = None
        self.card_type = card_type
        self.remaining_attempts = remaining_attempts

        if card_type == CardType.SLE4442:
            self.title("SLE4442 密码验证")
            self.psc_length = 3
            self._label_text = "请输入 SLE4442 PSC 密码（3 字节十六进制）："
        elif card_type == CardType.SLE4428:
            self.title("SLE4428 密码验证")
            self.psc_length = 2
            self._label_text = "请输入 SLE4428 PSC 密码（2 字节十六进制）："
        else:
            self.title("密码验证")
            self.psc_length = 3
            self._label_text = "请输入密码（十六进制）："

        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self._create_widgets()
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

        self.geometry(f"+{parent.winfo_rootx() + 200}+{parent.winfo_rooty() + 200}")
        if hasattr(self, 'byte_entries') and self.byte_entries:
            self.byte_entries[0].focus_set()

    def _create_widgets(self):
        frame = ttk.Frame(self, padding="20")
        frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        ttk.Label(frame, text=self._label_text, wraplength=300).grid(
            row=0, column=0, columnspan=self.psc_length, pady=(0, 10), sticky=tk.W
        )

        self.byte_entries = []
        self.byte_vars = []
        for i in range(self.psc_length):
            var = tk.StringVar(value="FF")
            entry = ttk.Entry(frame, textvariable=var, width=4, font=('Consolas', 11), justify='center')
            entry.grid(row=1, column=i, padx=5, pady=5)
            self.byte_entries.append(entry)
            self.byte_vars.append(var)
            
            # 使用 KeyPress 事件在输入前过滤
            entry.bind('<KeyPress>', self._on_key_press)
            entry.bind('<FocusOut>', self._on_focus_out)
            
            if i < self.psc_length - 1:
                ttk.Label(frame, text="-", font=('Consolas', 14)).grid(row=1, column=i, padx=(28, 0), sticky=tk.E)

        ttk.Label(frame, text="范围：00-FF", foreground="gray").grid(
            row=2, column=0, columnspan=self.psc_length, pady=(0, 5), sticky=tk.W
        )

        if self.remaining_attempts >= 0:
            max_attempts = 3 if self.card_type == CardType.SLE4442 else 8
            attempts_text = f"剩余校验次数：{self.remaining_attempts}/{max_attempts}"
            if self.remaining_attempts == 0:
                attempts_text += "  ⛔ 卡片已锁定！"
                fg_color = "red"
            elif self.remaining_attempts <= max_attempts // 3:
                attempts_text += "  ⚠ 极度危险！请谨慎输入！"
                fg_color = "red"
            elif self.remaining_attempts <= max_attempts // 2:
                attempts_text += "  ⚠ 请谨慎输入"
                fg_color = "orange"
            else:
                fg_color = "blue"
            ttk.Label(frame, text=attempts_text, foreground=fg_color, font=('', 9, 'bold')).grid(
                row=3, column=0, columnspan=self.psc_length, pady=(5, 10), sticky=tk.W
            )
            if self.remaining_attempts == 0:
                ttk.Label(frame, text="校验次数已耗尽，卡片已被永久锁定。\n无法继续验证密码或写入数据。", foreground="red").grid(
                    row=4, column=0, columnspan=self.psc_length, pady=(0, 10), sticky=tk.W
                )

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=5, column=0, columnspan=self.psc_length, pady=(5, 0))

        ttk.Button(btn_frame, text="验证", command=self._on_ok, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="取消", command=self._on_cancel, width=10).pack(side=tk.LEFT, padx=5)

    def _on_ok(self):
        try:
            hex_bytes = []
            for i, var in enumerate(self.byte_vars):
                byte_str = var.get().strip()
                if not byte_str:
                    messagebox.showerror("错误", f"第 {i+1} 个字节不能为空", parent=self)
                    return
                byte_val = int(byte_str, 16)
                if byte_val < 0 or byte_val > 255:
                    messagebox.showerror("错误", f"第 {i+1} 个字节超出范围 (00-FF)", parent=self)
                    return
                hex_bytes.append(byte_val)
            
            self.result = bytes(hex_bytes)
            self.destroy()
        except ValueError:
            messagebox.showerror("错误", "无效的十六进制格式", parent=self)

    def _on_cancel(self):
        self.result = None
        self.destroy()

    def _on_key_press(self, event):
        """在按键时过滤，只允许十六进制字符"""
        # 允许的控制键
        if event.keysym in ('BackSpace', 'Delete', 'Left', 'Right', 'Up', 'Down',
                           'Home', 'End', 'Return', 'Tab', 'Escape',
                           'Control_L', 'Control_R', 'Alt_L', 'Alt_R',
                           'Shift_L', 'Shift_R', 'Caps_Lock'):
            return
        
        # 允许 Ctrl 组合键（如 Ctrl+C, Ctrl+V, Ctrl+A 等）
        if event.state & 0x4:  # Ctrl 键按下
            return
        
        # 检查输入的字符
        char = event.char
        if not char:  # 特殊键，没有字符
            return
        
        # 只允许十六进制字符
        if char in '0123456789ABCDEFabcdef':
            # 自动转换为大写
            if char in 'abcdef':
                entry = event.widget
                # 阻止原始输入
                entry.after(0, lambda: self._insert_uppercase(entry, char.upper()))
                return "break"
            return  # 允许输入
        else:
            # 不允许的字符，阻止输入
            return "break"
    
    def _insert_uppercase(self, entry, char):
        """在光标位置插入大写字符"""
        cursor_pos = entry.index(tk.INSERT)
        entry.insert(cursor_pos, char)
    
    def _on_key_release(self, event):
        entry = event.widget
        text = entry.get().upper()
        text = ''.join(c for c in text if c in '0123456789ABCDEF')
        if len(text) > 2:
            text = text[:2]
        entry.delete(0, tk.END)
        entry.insert(0, text)

    def _on_focus_out(self, event):
        entry = event.widget
        text = entry.get().strip()
        if not text:
            entry.delete(0, tk.END)
            entry.insert(0, "00")
        else:
            try:
                val = int(text, 16)
                if val < 0 or val > 255:
                    entry.delete(0, tk.END)
                    entry.insert(0, "00")
            except ValueError:
                entry.delete(0, tk.END)
                entry.insert(0, "00")


class ChangePasswordDialog(tk.Toplevel):
    def __init__(self, parent, card_type: CardType):
        super().__init__(parent)
        self.result = None
        self.card_type = card_type

        if card_type == CardType.SLE4442:
            self.title("修改 SLE4442 密码")
            self.psc_length = 3
            self._label_text = "请输入新的 SLE4442 PSC 密码（3 字节十六进制）："
        elif card_type == CardType.SLE4428:
            self.title("修改 SLE4428 密码")
            self.psc_length = 2
            self._label_text = "请输入新的 SLE4428 PSC 密码（2 字节十六进制）："
        else:
            self.title("修改密码")
            self.psc_length = 3
            self._label_text = "请输入新密码（十六进制）："

        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()

        self._create_widgets()
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

        self.geometry(f"+{parent.winfo_rootx() + 200}+{parent.winfo_rooty() + 200}")
        if hasattr(self, 'new_byte_entries') and self.new_byte_entries:
            self.new_byte_entries[0].focus_set()

    def _create_widgets(self):
        frame = ttk.Frame(self, padding="20")
        frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        ttk.Label(frame, text=self._label_text, wraplength=300).grid(
            row=0, column=0, columnspan=self.psc_length, pady=(0, 10), sticky=tk.W
        )

        self.new_byte_entries = []
        self.new_byte_vars = []
        for i in range(self.psc_length):
            var = tk.StringVar(value="FF")
            entry = ttk.Entry(frame, textvariable=var, width=4, font=('Consolas', 11), justify='center')
            entry.grid(row=1, column=i, padx=5, pady=5)
            self.new_byte_entries.append(entry)
            self.new_byte_vars.append(var)
            
            # 使用 KeyPress 事件在输入前过滤
            entry.bind('<KeyPress>', self._on_key_press)
            entry.bind('<FocusOut>', self._on_focus_out)
            
            if i < self.psc_length - 1:
                ttk.Label(frame, text="-", font=('Consolas', 14)).grid(row=1, column=i, padx=(28, 0), sticky=tk.E)

        ttk.Label(frame, text=f"范围：00-FF（{self.psc_length} 字节）", foreground="gray").grid(
            row=2, column=0, columnspan=self.psc_length, pady=(0, 10), sticky=tk.W
        )

        ttk.Label(frame, text="⚠ 修改密码后请牢记新密码，忘记密码将无法恢复！", foreground="red").grid(
            row=3, column=0, columnspan=self.psc_length, pady=(10, 5), sticky=tk.W
        )

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=4, column=0, columnspan=self.psc_length, pady=(10, 0))

        ttk.Button(btn_frame, text="确认修改", command=self._on_ok, width=10).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="取消", command=self._on_cancel, width=10).pack(side=tk.LEFT, padx=5)

    def _on_key_press(self, event):
        """在按键时过滤，只允许十六进制字符"""
        # 允许的控制键
        if event.keysym in ('BackSpace', 'Delete', 'Left', 'Right', 'Up', 'Down',
                           'Home', 'End', 'Return', 'Tab', 'Escape',
                           'Control_L', 'Control_R', 'Alt_L', 'Alt_R',
                           'Shift_L', 'Shift_R', 'Caps_Lock'):
            return
        
        # 允许 Ctrl 组合键（如 Ctrl+C, Ctrl+V, Ctrl+A 等）
        if event.state & 0x4:  # Ctrl 键按下
            return
        
        # 检查输入的字符
        char = event.char
        if not char:  # 特殊键，没有字符
            return
        
        # 只允许十六进制字符
        if char in '0123456789ABCDEFabcdef':
            # 自动转换为大写
            if char in 'abcdef':
                entry = event.widget
                # 阻止原始输入
                entry.after(0, lambda: self._insert_uppercase(entry, char.upper()))
                return "break"
            return  # 允许输入
        else:
            # 不允许的字符，阻止输入
            return "break"
    
    def _insert_uppercase(self, entry, char):
        """在光标位置插入大写字符"""
        cursor_pos = entry.index(tk.INSERT)
        entry.insert(cursor_pos, char)

    def _on_key_release(self, event):
        entry = event.widget
        text = entry.get().upper()
        text = ''.join(c for c in text if c in '0123456789ABCDEF')
        if len(text) > 2:
            text = text[:2]
        entry.delete(0, tk.END)
        entry.insert(0, text)

    def _on_focus_out(self, event):
        entry = event.widget
        text = entry.get().strip()
        if not text:
            entry.delete(0, tk.END)
            entry.insert(0, "00")
        else:
            try:
                val = int(text, 16)
                if val < 0 or val > 255:
                    entry.delete(0, tk.END)
                    entry.insert(0, "00")
            except ValueError:
                entry.delete(0, tk.END)
                entry.insert(0, "00")

    def _get_bytes_from_vars(self, vars_list, prefix=""):
        try:
            hex_bytes = []
            for i, var in enumerate(vars_list):
                byte_str = var.get().strip()
                if not byte_str:
                    messagebox.showerror("错误", f"{prefix}第 {i+1} 个字节不能为空", parent=self)
                    return None
                byte_val = int(byte_str, 16)
                if byte_val < 0 or byte_val > 255:
                    messagebox.showerror("错误", f"{prefix}第 {i+1} 个字节超出范围 (00-FF)", parent=self)
                    return None
                hex_bytes.append(byte_val)
            return bytes(hex_bytes)
        except ValueError:
            messagebox.showerror("错误", f"{prefix}无效的十六进制格式", parent=self)
            return None

    def _on_ok(self):
        new_bytes = self._get_bytes_from_vars(self.new_byte_vars)
        if new_bytes is None:
            return

        self.result = new_bytes
        self.destroy()

    def _on_cancel(self):
        self.result = None
        self.destroy()
