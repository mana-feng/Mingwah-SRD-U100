"""
卡片数据编辑器弹窗
支持查看、编辑和写入卡片数据
密码验证卡片需先验证密码才能编辑
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import os
from src.core.types import CardType, CardFullData, get_card_memory_info
from src.core.constants import IC_OK, IC_ERR
from src.gui.password_dialogs import PasswordDialog, ChangePasswordDialog


class CardDataEditor(tk.Toplevel):
    BYTES_PER_LINE = 16

    def __init__(self, parent, detector, card_data: CardFullData, log_callback=None):
        super().__init__(parent)
        self.detector = detector
        self.card_data = card_data
        self.log_callback = log_callback
        self.password_verified = False
        self.current_password = None
        self._modified = False

        card_type = card_data.card_type
        mem_info = card_data.memory_info
        title = f"卡片数据编辑器 - {card_type.name}"
        if mem_info and mem_info.description:
            title += f" ({mem_info.description})"
        self.title(title)
        self.geometry("1000x600")

        self._original_main = bytearray(card_data.main_data) if card_data.main_data else bytearray()
        self._original_protection = bytearray(card_data.protection_data) if card_data.protection_data else bytearray()
        self._original_security = bytearray(card_data.security_data) if card_data.security_data else bytearray()

        self._editable = self._determine_editable()

        self._remaining_attempts = -1
        if self.card_data.card_type in (CardType.SLE4442, CardType.SLE4428):
            if self.card_data.remaining_attempts >= 0:
                self._remaining_attempts = self.card_data.remaining_attempts
            else:
                self._remaining_attempts = self._read_remaining_attempts()

        self._create_widgets()
        self._populate_data()

        self.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _determine_editable(self) -> bool:
        card_type = self.card_data.card_type
        if card_type in (CardType.SLE4442, CardType.SLE4428):
            return False
        return True

    def _create_widgets(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        info_frame = ttk.Frame(self, padding="5")
        info_frame.grid(row=0, column=0, sticky=(tk.W, tk.E))

        mem_info = self.card_data.memory_info
        if mem_info:
            ttk.Label(info_frame, text=f"卡片: {self.card_data.card_type.name}", font=('', 10, 'bold')).pack(side=tk.LEFT, padx=5)
            ttk.Label(info_frame, text=f"容量: {mem_info.total_bytes} 字节", foreground="gray").pack(side=tk.LEFT, padx=10)
            if mem_info.has_protection:
                ttk.Label(info_frame, text=f"保护位: {mem_info.protection_bytes} 字节", foreground="gray").pack(side=tk.LEFT, padx=10)
            if mem_info.has_security_memory:
                ttk.Label(info_frame, text=f"安全存储器: {mem_info.security_memory_size} 字节", foreground="gray").pack(side=tk.LEFT, padx=10)

        self.verify_status_var = tk.StringVar(value="")
        self.verify_status_label = ttk.Label(info_frame, textvariable=self.verify_status_var, foreground="#CC6600")
        self.verify_status_label.pack(side=tk.RIGHT, padx=10)

        if self.card_data.card_type in (CardType.SLE4442, CardType.SLE4428):
            attempts_text = self._format_attempts_text(self._remaining_attempts)
            self.verify_status_var.set(f"⚠ 需要验证密码才能编辑  {attempts_text}")
            self.change_pwd_btn = ttk.Button(info_frame, text="修改密码", command=self._change_password, state='disabled')
            self.change_pwd_btn.pack(side=tk.RIGHT, padx=5)
            ttk.Button(info_frame, text="验证密码", command=self._verify_password).pack(side=tk.RIGHT, padx=5)

        notebook = ttk.Notebook(self)
        notebook.grid(row=1, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)

        main_frame = ttk.Frame(notebook)
        notebook.add(main_frame, text=f"主存储器 ({len(self._original_main)} 字节)")
        self._create_hex_editor(main_frame, 'main')

        if self._original_protection:
            pro_frame = ttk.Frame(notebook)
            notebook.add(pro_frame, text=f"保护位 ({len(self._original_protection)} 字节)")
            self._create_hex_editor(pro_frame, 'protection')

        if self._original_security:
            sec_frame = ttk.Frame(notebook)
            notebook.add(sec_frame, text=f"安全存储器 ({len(self._original_security)} 字节)")
            self._create_hex_editor(sec_frame, 'security')

        bottom_frame = ttk.Frame(self, padding="5")
        bottom_frame.grid(row=2, column=0, sticky=(tk.W, tk.E))

        self.modified_var = tk.StringVar(value="")
        ttk.Label(bottom_frame, textvariable=self.modified_var, foreground="red").pack(side=tk.LEFT, padx=5)

        ttk.Button(bottom_frame, text="刷新数据", command=self._refresh_data, width=10).pack(side=tk.RIGHT, padx=5)
        ttk.Button(bottom_frame, text="写入修改", command=self._write_changes, width=10).pack(side=tk.RIGHT, padx=5)
        ttk.Button(bottom_frame, text="导入文件", command=self._import_file, width=10).pack(side=tk.RIGHT, padx=5)
        ttk.Button(bottom_frame, text="导出文件", command=self._export_file, width=10).pack(side=tk.RIGHT, padx=5)

    def _create_hex_editor(self, parent, data_key: str):
        container = ttk.Frame(parent)
        container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        header = ttk.Frame(container)
        header.pack(fill=tk.X)
        ttk.Label(header, text="偏移", width=8, font=('Consolas', 12, 'bold')).pack(side=tk.LEFT)
        for i in range(self.BYTES_PER_LINE):
            ttk.Label(header, text=f"{i:02X}", width=4, font=('Consolas', 12, 'bold')).pack(side=tk.LEFT)
        ttk.Label(header, text="  ASCII", font=('Consolas', 12, 'bold')).pack(side=tk.LEFT, padx=(10, 0))

        canvas = tk.Canvas(container, borderwidth=0, highlightthickness=0)
        v_scroll = ttk.Scrollbar(container, orient=tk.VERTICAL, command=canvas.yview)

        scroll_frame = ttk.Frame(canvas)
        scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        canvas_window = canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=v_scroll.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        v_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        def _on_canvas_configure(event):
            canvas.itemconfig(canvas_window, width=event.width)

        canvas.bind("<Configure>", _on_canvas_configure)

        data = getattr(self, f'_original_{data_key}', bytearray())
        entries = []
        ascii_labels = []

        num_lines = (len(data) + self.BYTES_PER_LINE - 1) // self.BYTES_PER_LINE

        for line_idx in range(num_lines):
            row_frame = ttk.Frame(scroll_frame)
            row_frame.pack(fill=tk.X)

            offset = line_idx * self.BYTES_PER_LINE
            ttk.Label(row_frame, text=f"{offset:04X}", width=8, font=('Consolas', 12)).pack(side=tk.LEFT)

            line_entries = []
            for byte_idx in range(self.BYTES_PER_LINE):
                data_idx = offset + byte_idx
                var = tk.StringVar()

                if data_idx < len(data):
                    var.set(f"{data[data_idx]:02X}")

                entry = tk.Entry(
                    row_frame, textvariable=var, width=4,
                    font=('Consolas', 12), justify=tk.CENTER,
                    borderwidth=1, relief=tk.SOLID
                )
                entry.pack(side=tk.LEFT)
                entry.data_idx = data_idx
                entry.data_key = data_key
                entry.bind('<KeyRelease>', self._on_cell_edit)
                entry.bind('<FocusOut>', self._on_cell_validate)
                entry.bind('<Return>', self._on_cell_next)
                entry.bind('<Tab>', self._on_cell_next)

                if data_idx >= len(data):
                    entry.config(state='disabled')

                line_entries.append((data_idx, var, entry))

            ascii_var = tk.StringVar()
            self._update_ascii_label(ascii_var, data, offset)
            ascii_label = ttk.Label(row_frame, textvariable=ascii_var, width=20, font=('Consolas', 12))
            ascii_label.pack(side=tk.LEFT, padx=(10, 0))

            entries.extend(line_entries)
            ascii_labels.append((offset, ascii_var))

        setattr(self, f'_entries_{data_key}', entries)
        setattr(self, f'_ascii_labels_{data_key}', ascii_labels)
        setattr(self, f'_canvas_{data_key}', canvas)

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _on_enter(event):
            canvas.bind_all("<MouseWheel>", _on_mousewheel)

        def _on_leave(event):
            canvas.unbind_all("<MouseWheel>")

        canvas.bind("<Enter>", _on_enter)
        canvas.bind("<Leave>", _on_leave)

    def _update_ascii_label(self, ascii_var, data, offset):
        chunk = data[offset:offset + self.BYTES_PER_LINE]
        ascii_str = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
        ascii_var.set(ascii_str)

    def _on_cell_edit(self, event):
        entry = event.widget
        text = entry.get().upper()
        text = ''.join(c for c in text if c in '0123456789ABCDEF')
        if len(text) > 2:
            text = text[:2]
        entry.delete(0, tk.END)
        entry.insert(0, text)

        self._update_cell_color(entry)

    def _update_cell_color(self, entry):
        data_key = getattr(entry, 'data_key', None)
        data_idx = getattr(entry, 'data_idx', -1)
        if data_key is None or data_idx < 0:
            return

        original = getattr(self, f'_original_{data_key}', bytearray())
        if data_idx >= len(original):
            return

        text = entry.get().strip()
        if not text:
            entry.config(foreground="black")
            return

        try:
            current_val = int(text, 16)
            original_val = original[data_idx]
            if current_val != original_val:
                entry.config(foreground="#006400")
            else:
                entry.config(foreground="black")
        except ValueError:
            entry.config(foreground="black")

    def _on_cell_validate(self, event):
        entry = event.widget
        text = entry.get().strip()
        if not text:
            return
        try:
            val = int(text, 16)
            if val < 0 or val > 255:
                entry.delete(0, tk.END)
                entry.insert(0, "00")
        except ValueError:
            entry.delete(0, tk.END)
            entry.insert(0, "00")

        self._update_cell_color(entry)

    def _on_cell_next(self, event):
        entry = event.widget
        entry.event_generate('<Tab>')

    def _read_remaining_attempts(self) -> int:
        try:
            if self.card_data.security_data and len(self.card_data.security_data) >= 1:
                err_byte = self.card_data.security_data[0]
                if self.card_data.card_type == CardType.SLE4442:
                    mask = 0x07
                elif self.card_data.card_type == CardType.SLE4428:
                    mask = 0xFF
                else:
                    mask = 0xFF
                attempts = bin(err_byte & mask).count('1')
                print(f"[DEBUG] _read_remaining_attempts: 从 security_data 读取, data={self.card_data.security_data.hex()}, attempts={attempts}")
                return attempts
            result = self.detector.get_remaining_attempts()
            print(f"[DEBUG] _read_remaining_attempts: detector 返回 {result}")
            if result >= 0:
                return result
            return -1
        except Exception as e:
            print(f"[DEBUG] _read_remaining_attempts 异常: {e}")
            return -1

    def _get_max_attempts(self) -> int:
        if self.card_data.card_type == CardType.SLE4442:
            return 3
        elif self.card_data.card_type == CardType.SLE4428:
            return 8
        return 8

    def _format_attempts_text(self, attempts: int) -> str:
        max_attempts = self._get_max_attempts()
        if attempts < 0:
            return "[剩余校验次数: 未知]"
        elif attempts == 0:
            return f"[剩余校验次数: 0/{max_attempts} ⛔ 已锁定]"
        elif attempts <= max_attempts // 3:
            return f"[剩余校验次数: {attempts}/{max_attempts} ⚠ 危险]"
        elif attempts <= max_attempts // 2:
            return f"[剩余校验次数: {attempts}/{max_attempts} ⚠ 警告]"
        else:
            return f"[剩余校验次数: {attempts}/{max_attempts}]"

    def _populate_data(self):
        pass

    def _collect_edited_data(self, data_key: str) -> bytearray:
        entries = getattr(self, f'_entries_{data_key}', [])
        data = bytearray(getattr(self, f'_original_{data_key}', bytearray()))

        for data_idx, var, entry in entries:
            if data_idx >= len(data):
                continue
            text = var.get().strip()
            if text:
                try:
                    val = int(text, 16)
                    if 0 <= val <= 255:
                        data[data_idx] = val
                except ValueError:
                    pass

        return data

    def _check_modified(self) -> bool:
        for key in ('main', 'protection', 'security'):
            original = getattr(self, f'_original_{key}', bytearray())
            edited = self._collect_edited_data(key)
            if edited != original:
                return True
        return False

    def _verify_password(self):
        if self._remaining_attempts == 0:
            messagebox.showerror("卡片已锁定", "密码校验次数已耗尽，卡片已被永久锁定！\n无法继续验证密码。", parent=self)
            return

        dialog = PasswordDialog(self, self.card_data.card_type, remaining_attempts=self._remaining_attempts)
        self.wait_window(dialog)

        if dialog.result is None:
            return

        password = dialog.result

        def verify_thread():
            success = self.detector.verify_card_password(password)
            self.after(0, lambda: self._on_verify_result(success, password))

        threading.Thread(target=verify_thread, daemon=True).start()

    def _change_password(self):
        print(f"[DEBUG] [CHANGE_PWD] 开始修改密码流程")
        print(f"[DEBUG] [CHANGE_PWD] password_verified={self.password_verified}, remaining_attempts={self._remaining_attempts}")
        if not self.password_verified:
            messagebox.showwarning("需要验证", "请先验证当前密码才能修改密码", parent=self)
            return

        if self._remaining_attempts == 0:
            messagebox.showerror("卡片已锁定", "密码校验次数已耗尽，无法修改密码", parent=self)
            return

        dialog = ChangePasswordDialog(self, self.card_data.card_type)
        self.wait_window(dialog)

        if dialog.result is None:
            print(f"[DEBUG] [CHANGE_PWD] 用户取消输入")
            return

        new_password = dialog.result
        print(f"[DEBUG] [CHANGE_PWD] 用户输入新密码：{new_password.hex().upper()}")

        if not messagebox.askyesno(
            "确认修改密码",
            f"确定要修改卡片密码吗？\n\n"
            f"新密码: {new_password.hex().upper()}\n\n"
            f"⚠ 修改后请牢记新密码，忘记密码将无法恢复！",
            parent=self
        ):
            print(f"[DEBUG] [CHANGE_PWD] 用户取消确认")
            return

        print(f"[DEBUG] [CHANGE_PWD] 开始调用 detector.change_card_password")
        
        def change_thread():
            try:
                print(f"[DEBUG] [CHANGE_PWD] 线程：调用 change_card_password, new_password={new_password.hex().upper()}")
                success = self.detector.change_card_password(self.current_password, new_password)
                print(f"[DEBUG] [CHANGE_PWD] 线程：change_card_password 返回 success={success}")
                self.after(0, lambda: self._on_change_password_result(success, new_password))
            except Exception as e:
                print(f"[DEBUG] [CHANGE_PWD] 线程异常：{e}")
                self.after(0, lambda: self._on_change_password_result(False, new_password))

        threading.Thread(target=change_thread, daemon=True).start()

    def _on_change_password_result(self, success: bool, new_password: bytes):
        if success:
            self.current_password = new_password
            if self.log_callback:
                self.log_callback(f"卡片密码修改成功，新密码: {new_password.hex().upper()}", "SUCCESS")
            messagebox.showinfo("修改成功", f"密码已成功修改！\n新密码: {new_password.hex().upper()}\n\n请牢记新密码！", parent=self)
        else:
            if self.log_callback:
                self.log_callback("密码修改失败", "ERROR")
            messagebox.showerror("修改失败", "密码修改失败！\n请确认密码验证状态是否有效。", parent=self)

    def _on_verify_result(self, success: bool, password: bytes = None):
        if success:
            self.password_verified = True
            self.current_password = password
            self._editable = True
            max_attempts = self._get_max_attempts()
            self._remaining_attempts = max_attempts
            self.verify_status_var.set(f"✓ 密码验证通过，可以编辑  剩余校验次数: {max_attempts}/{max_attempts}")
            self.verify_status_label.config(foreground="green")
            self.modified_var.set("")
            if hasattr(self, 'change_pwd_btn'):
                self.change_pwd_btn.config(state='normal')
            if self.log_callback:
                self.log_callback("卡片密码验证通过", "SUCCESS")
        else:
            self.password_verified = False
            self.current_password = None
            self._remaining_attempts = self._read_remaining_attempts()
            attempts_text = self._format_attempts_text(self._remaining_attempts)
            if self._remaining_attempts == 0:
                self.verify_status_var.set(f"✗ 密码验证失败  {attempts_text}")
                self.verify_status_label.config(foreground="red")
                if self.log_callback:
                    self.log_callback("密码验证失败，卡片已锁定（校验次数耗尽）！", "ERROR")
                messagebox.showerror("卡片已锁定", "密码校验次数已耗尽，卡片已被永久锁定！\n无法继续验证密码或写入数据。", parent=self)
            else:
                self.verify_status_var.set(f"✗ 密码验证失败  {attempts_text}")
                self.verify_status_label.config(foreground="red")
                if self.log_callback:
                    self.log_callback(f"密码验证失败，{attempts_text}", "ERROR")

    def _refresh_data(self):
        def refresh_thread():
            card_result = self.detector.read_card_full_data()
            self.after(0, lambda: self._on_refresh_result(card_result))

        threading.Thread(target=refresh_thread, daemon=True).start()

    def _on_refresh_result(self, card_result: CardFullData):
        if not card_result.success:
            if self.log_callback:
                self.log_callback(f"刷新数据失败: {card_result.error_message}", "ERROR")
            return

        self.card_data = card_result
        self._original_main = bytearray(card_result.main_data) if card_result.main_data else bytearray()
        self._original_protection = bytearray(card_result.protection_data) if card_result.protection_data else bytearray()
        self._original_security = bytearray(card_result.security_data) if card_result.security_data else bytearray()

        for key in ('main', 'protection', 'security'):
            entries = getattr(self, f'_entries_{key}', [])
            data = getattr(self, f'_original_{key}', bytearray())
            ascii_labels = getattr(self, f'_ascii_labels_{key}', [])

            for data_idx, var, entry in entries:
                if data_idx < len(data):
                    var.set(f"{data[data_idx]:02X}")
                    entry.config(state='normal', foreground="black")
                else:
                    var.set("")
                    entry.config(state='disabled')

            for offset, ascii_var in ascii_labels:
                self._update_ascii_label(ascii_var, data, offset)

        self._modified = False
        self.modified_var.set("")
        if self.log_callback:
            self.log_callback("卡片数据已刷新", "SUCCESS")

    def _write_changes(self):
        if not self._editable:
            card_type = self.card_data.card_type
            if card_type in (CardType.SLE4442, CardType.SLE4428):
                messagebox.showwarning("需要验证", "请先验证卡片密码才能写入数据", parent=self)
                return
            elif card_type in (CardType.MIFARE_S50, CardType.MIFARE_S70):
                messagebox.showwarning("需要密钥", "请先输入 Mifare 密钥才能写入数据", parent=self)
                return
            else:
                messagebox.showwarning("不可编辑", "当前卡片类型不支持写入", parent=self)
                return

        if not self._check_modified():
            messagebox.showinfo("提示", "数据未修改，无需写入", parent=self)
            return

        if not messagebox.askyesno("确认写入", "确定要将修改的数据写入卡片吗？\n此操作不可撤销！", parent=self):
            return

        self._do_write()

    def _do_write(self):
        self._write_normal()

    def _write_normal(self):
        edited_main = self._collect_edited_data('main')
        edited_protection = self._collect_edited_data('protection')

        errors = []

        def write_thread():
            if edited_main != self._original_main:
                for offset in range(0, len(edited_main), 32):
                    old_chunk = self._original_main[offset:offset + 32]
                    new_chunk = edited_main[offset:offset + 32]
                    if old_chunk != new_chunk:
                        st = self.detector.write_card_data(offset, bytes(new_chunk))
                        if st != IC_OK:
                            errors.append(f"写入主存储器偏移 {offset:04X} 失败 (返回值: {st})")

            if edited_protection and edited_protection != self._original_protection:
                for offset in range(0, len(edited_protection), 32):
                    old_chunk = self._original_protection[offset:offset + 32]
                    new_chunk = edited_protection[offset:offset + 32]
                    if old_chunk != new_chunk:
                        st = self.detector.write_card_protection(offset, bytes(new_chunk))
                        if st != IC_OK:
                            errors.append(f"写入保护位偏移 {offset:04X} 失败 (返回值: {st})")

            self.after(0, self._on_write_complete, errors)

        threading.Thread(target=write_thread, daemon=True).start()

    def _on_write_complete(self, errors: list):
        if errors:
            error_msg = '\n'.join(errors)
            if self.log_callback:
                self.log_callback(f"写入部分失败:\n{error_msg}", "ERROR")
            messagebox.showerror("写入错误", f"部分数据写入失败:\n{error_msg}", parent=self)
        else:
            self._original_main = self._collect_edited_data('main')
            self._original_protection = self._collect_edited_data('protection')
            self._original_security = self._collect_edited_data('security')
            self._modified = False
            self.modified_var.set("")
            self._update_all_colors()
            if self.log_callback:
                self.log_callback("卡片数据写入成功", "SUCCESS")
            messagebox.showinfo("成功", "数据已成功写入卡片", parent=self)

    def _export_file(self):
        card_type_name = self.card_data.card_type.name

        file_path = filedialog.asksaveasfilename(
            parent=self,
            title="导出卡片数据",
            initialfile=f"{card_type_name}_data",
            defaultextension=".dump",
            filetypes=[
                ("Dump 文件", "*.dump"),
                ("二进制文件", "*.bin"),
                ("十六进制文件", "*.hex"),
                ("所有文件", "*.*"),
            ]
        )

        if not file_path:
            return

        try:
            main_data = self._collect_edited_data('main')
            protection_data = self._collect_edited_data('protection')
            security_data = self._collect_edited_data('security')

            ext = os.path.splitext(file_path)[1].lower()

            if ext == '.hex':
                self._export_hex_file(file_path, main_data, protection_data, security_data)
            else:
                self._export_binary_file(file_path, main_data, protection_data, security_data)

            if self.log_callback:
                self.log_callback(f"数据已导出到: {file_path}", "SUCCESS")
            messagebox.showinfo("导出成功", f"卡片数据已导出到:\n{file_path}", parent=self)
        except Exception as e:
            if self.log_callback:
                self.log_callback(f"导出文件失败: {e}", "ERROR")
            messagebox.showerror("导出失败", f"导出文件时出错:\n{e}", parent=self)

    def _export_binary_file(self, file_path, main_data, protection_data, security_data):
        with open(file_path, 'wb') as f:
            f.write(main_data)
            if protection_data:
                f.write(protection_data)
            if security_data:
                f.write(security_data)

    def _export_hex_file(self, file_path, main_data, protection_data, security_data):
        with open(file_path, 'w', encoding='ascii') as f:
            all_data = bytearray(main_data)
            if protection_data:
                all_data.extend(protection_data)
            if security_data:
                all_data.extend(security_data)

            for offset in range(0, len(all_data), 16):
                chunk = all_data[offset:offset + 16]
                hex_part = ' '.join(f'{b:02X}' for b in chunk)
                ascii_part = ''.join(chr(b) if 32 <= b < 127 else '.' for b in chunk)
                f.write(f'{offset:04X}: {hex_part:<48s} {ascii_part}\n')

    def _import_file(self):
        file_path = filedialog.askopenfilename(
            parent=self,
            title="导入卡片数据",
            filetypes=[
                ("所有支持的文件", "*.dump *.bin *.hex"),
                ("Dump 文件", "*.dump"),
                ("二进制文件", "*.bin"),
                ("十六进制文件", "*.hex"),
                ("所有文件", "*.*"),
            ]
        )

        if not file_path:
            return

        try:
            ext = os.path.splitext(file_path)[1].lower()

            if ext == '.hex':
                file_data = self._import_hex_file(file_path)
            else:
                with open(file_path, 'rb') as f:
                    file_data = bytearray(f.read())

            if not file_data:
                messagebox.showwarning("导入失败", "文件内容为空", parent=self)
                return

            editor_size = len(self._original_main)
            if self._original_protection:
                editor_size += len(self._original_protection)
            if self._original_security:
                editor_size += len(self._original_security)

            file_size = len(file_data)

            if file_size != editor_size:
                proceed = messagebox.askyesno(
                    "位数不匹配",
                    f"文件大小与编辑器数据大小不一致！\n\n"
                    f"编辑器数据大小: {editor_size} 字节\n"
                    f"文件数据大小: {file_size} 字节\n\n"
                    f"是否继续导入？\n"
                    f"（数据将按编辑器大小进行截取或补零）",
                    parent=self
                )
                if not proceed:
                    return

            self._apply_imported_data(file_data, editor_size)

            if self.log_callback:
                self.log_callback(f"数据已从文件导入: {file_path}", "SUCCESS")
        except Exception as e:
            if self.log_callback:
                self.log_callback(f"导入文件失败: {e}", "ERROR")
            messagebox.showerror("导入失败", f"导入文件时出错:\n{e}", parent=self)

    def _import_hex_file(self, file_path) -> bytearray:
        data = bytearray()
        with open(file_path, 'r', encoding='ascii', errors='replace') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                if ':' in line:
                    hex_part = line.split(':', 1)[1].strip()
                    if '  ' in hex_part:
                        hex_part = hex_part.split('  ')[0].strip()
                    hex_bytes = hex_part.replace(' ', '')
                    try:
                        data.extend(bytes.fromhex(hex_bytes))
                    except ValueError:
                        continue
        return data

    def _apply_imported_data(self, file_data: bytearray, editor_size: int):
        main_len = len(self._original_main)
        pro_len = len(self._original_protection) if self._original_protection else 0
        sec_len = len(self._original_security) if self._original_security else 0

        padded = bytearray(editor_size)
        copy_len = min(len(file_data), editor_size)
        padded[:copy_len] = file_data[:copy_len]

        new_main = padded[:main_len]
        new_protection = padded[main_len:main_len + pro_len] if pro_len > 0 else bytearray()
        new_security = padded[main_len + pro_len:main_len + pro_len + sec_len] if sec_len > 0 else bytearray()

        self._set_editor_data('main', new_main, self._original_main)
        if pro_len > 0:
            self._set_editor_data('protection', new_protection, self._original_protection)
        if sec_len > 0:
            self._set_editor_data('security', new_security, self._original_security)

        self._update_all_colors()

        self._modified = self._check_modified()
        if self._modified:
            self.modified_var.set("数据已修改（导入文件）")
        else:
            self.modified_var.set("")

    def _set_editor_data(self, data_key: str, new_data: bytearray, original_data: bytearray):
        entries = getattr(self, f'_entries_{data_key}', [])
        ascii_labels = getattr(self, f'_ascii_labels_{data_key}', [])

        for data_idx, var, entry in entries:
            if data_idx < len(new_data):
                var.set(f"{new_data[data_idx]:02X}")
                entry.config(state='normal')
            else:
                var.set("")
                entry.config(state='disabled')

        for offset, ascii_var in ascii_labels:
            self._update_ascii_label(ascii_var, new_data, offset)

    def _update_all_colors(self):
        for key in ('main', 'protection', 'security'):
            self._update_data_colors(key)

    def _update_data_colors(self, data_key: str):
        entries = getattr(self, f'_entries_{data_key}', [])
        original = getattr(self, f'_original_{data_key}', bytearray())

        for data_idx, var, entry in entries:
            if data_idx >= len(original):
                continue
            text = var.get().strip()
            if not text:
                continue
            try:
                current_val = int(text, 16)
                original_val = original[data_idx]
                if current_val != original_val:
                    entry.config(foreground="#006400")
                else:
                    entry.config(foreground="black")
            except ValueError:
                entry.config(foreground="black")

    def force_close(self):
        self._force_destroy = True
        self.destroy()

    def _on_closing(self):
        if self._check_modified():
            if not messagebox.askyesno("未保存的修改", "数据已修改但未写入卡片，确定要关闭吗？", parent=self):
                return
        self.destroy()
