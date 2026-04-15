"""
卡片探测器 GUI 应用
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from src.core.mwic import MWIC32
from src.core.detector import AutoCardDetector
from src.core.types import DeviceStatus, CardType, CardFullData, get_card_memory_info
from src.gui.card_editor import CardDataEditor
from src.core.constants import IC_OK, IC_ERR, IC_ERR_NO_CARD, IC_ERR_PORT


class CardDetectorGUI:

    def __init__(self, root):
        self.root = root
        self.root.title("明华澳汉 接触式磁卡读卡器软件 --manafeng")
        self.root.geometry("850x650")

        self.mwic = MWIC32()
        self.detector = AutoCardDetector(self.mwic)
        self.is_detecting = False
        self._editor_windows = []

        self._create_menu()
        self._create_widgets()

        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)

        self.root.after(500, self._auto_search_port)

    def _create_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="文件", menu=file_menu)
        file_menu.add_command(label="连接读写器", command=self._connect_device)
        file_menu.add_command(label="断开连接", command=self._disconnect_device)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self._on_closing)

        ops_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="操作", menu=ops_menu)
        ops_menu.add_command(label="开始自动检测", command=self._start_detection)
        ops_menu.add_command(label="停止自动检测", command=self._stop_detection)
        ops_menu.add_separator()
        ops_menu.add_command(label="手动检测", command=self._manual_detect)
        ops_menu.add_command(label="读取卡片信息", command=self._read_card_info)
        ops_menu.add_command(label="读取卡片数据", command=self._read_card_data)

        tools_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="工具", menu=tools_menu)
        tools_menu.add_command(label="自动搜索端口", command=self._auto_search_port)
        tools_menu.add_command(label="蜂鸣器测试", command=self._beep_test)

        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="帮助", menu=help_menu)
        help_menu.add_command(label="关于", command=self._show_about)

    def _create_widgets(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.rowconfigure(4, weight=1)

        device_frame = ttk.LabelFrame(main_frame, text="设备状态", padding="5")
        device_frame.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=5)
        device_frame.columnconfigure(1, weight=1)

        ttk.Label(device_frame, text="连接状态:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.status_label = ttk.Label(device_frame, text="未连接", foreground="red")
        self.status_label.grid(row=0, column=1, sticky=tk.W, padx=5)

        ttk.Label(device_frame, text="端口类型:").grid(row=0, column=2, sticky=tk.W, padx=5)
        self.port_var = tk.StringVar(value="COM1")
        port_combo = ttk.Combobox(device_frame, textvariable=self.port_var, width=8)
        port_combo['values'] = ('COM1', 'COM2', 'COM3', 'COM4', 'USB', 'HID')
        port_combo.grid(row=0, column=3, sticky=tk.W, padx=5)

        ttk.Label(device_frame, text="波特率:").grid(row=0, column=4, sticky=tk.W, padx=5)
        self.baud_var = tk.StringVar(value="9600")
        baud_combo = ttk.Combobox(device_frame, textvariable=self.baud_var, width=8)
        baud_combo['values'] = ('1200', '2400', '4800', '9600', '19200', '38400', '57600', '115200')
        baud_combo.grid(row=0, column=5, sticky=tk.W, padx=5)

        self.connect_btn = ttk.Button(device_frame, text="连接", command=self._connect_device)
        self.connect_btn.grid(row=0, column=6, padx=10)

        ttk.Label(device_frame, text="硬件版本:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.hw_ver_label = ttk.Label(device_frame, text="-", foreground="gray")
        self.hw_ver_label.grid(row=1, column=1, sticky=tk.W, padx=5)

        ttk.Label(device_frame, text="固件版本:").grid(row=1, column=2, sticky=tk.W, padx=5, pady=5)
        self.fw_ver_label = ttk.Label(device_frame, text="-", foreground="gray")
        self.fw_ver_label.grid(row=1, column=3, sticky=tk.W, padx=5)

        card_frame = ttk.LabelFrame(main_frame, text="卡片状态", padding="5")
        card_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), pady=5)
        card_frame.columnconfigure(1, weight=1)

        ttk.Label(card_frame, text="卡片状态:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.card_status_label = ttk.Label(card_frame, text="无卡", foreground="gray")
        self.card_status_label.grid(row=0, column=1, sticky=tk.W, padx=5)

        ttk.Label(card_frame, text="卡片类型:").grid(row=0, column=2, sticky=tk.W, padx=5)
        self.card_type_label = ttk.Label(card_frame, text="-", foreground="gray")
        self.card_type_label.grid(row=0, column=3, sticky=tk.W, padx=5)

        ttk.Label(card_frame, text="序列号:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.snr_label = ttk.Label(card_frame, text="-", foreground="gray", font=('Consolas', 10))
        self.snr_label.grid(row=1, column=1, columnspan=3, sticky=tk.W, padx=5)

        ttk.Label(card_frame, text="版本信息:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        self.ver_label = ttk.Label(card_frame, text="-", foreground="gray", font=('Consolas', 10))
        self.ver_label.grid(row=2, column=1, columnspan=3, sticky=tk.W, padx=5)

        control_frame = ttk.Frame(main_frame)
        control_frame.grid(row=2, column=0, sticky=(tk.W, tk.E), pady=10)

        self.auto_detect_btn = ttk.Button(
            control_frame, text="开始自动检测", command=self._start_detection, width=15
        )
        self.auto_detect_btn.pack(side=tk.LEFT, padx=5)

        self.manual_detect_btn = ttk.Button(
            control_frame, text="手动检测", command=self._manual_detect, width=15
        )
        self.manual_detect_btn.pack(side=tk.LEFT, padx=5)

        self.read_card_btn = ttk.Button(
            control_frame, text="读取卡片信息", command=self._read_card_info, width=15
        )
        self.read_card_btn.pack(side=tk.LEFT, padx=5)

        self.read_data_btn = ttk.Button(
            control_frame, text="读取卡片数据", command=self._read_card_data, width=15
        )
        self.read_data_btn.pack(side=tk.LEFT, padx=5)

        self.beep_btn = ttk.Button(
            control_frame, text="蜂鸣器测试", command=self._beep_test, width=15
        )
        self.beep_btn.pack(side=tk.LEFT, padx=5)

        self.clear_log_btn = ttk.Button(
            control_frame, text="清空日志", command=self._clear_log, width=15
        )
        self.clear_log_btn.pack(side=tk.LEFT, padx=5)

        log_frame = ttk.LabelFrame(main_frame, text="操作日志", padding="5")
        log_frame.grid(row=4, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), pady=5)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log_text = scrolledtext.ScrolledText(
            log_frame, height=15, width=100, font=('Consolas', 9)
        )
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        self.status_var = tk.StringVar(value="就绪")
        status_bar = ttk.Label(
            main_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W
        )
        status_bar.grid(row=5, column=0, sticky=(tk.W, tk.E), pady=5)

    def _log(self, message: str, level: str = "INFO"):
        timestamp = time.strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] [{level}] {message}\n"
        self.log_text.insert(tk.END, log_entry)
        self.log_text.see(tk.END)
        if level == "ERROR":
            self.log_text.tag_add("error", "end-2c linestart", "end-1c")
            self.log_text.tag_config("error", foreground="red")
        elif level == "SUCCESS":
            self.log_text.tag_add("success", "end-2c linestart", "end-1c")
            self.log_text.tag_config("success", foreground="green")
        elif level == "WARNING":
            self.log_text.tag_add("warning", "end-2c linestart", "end-1c")
            self.log_text.tag_config("warning", foreground="orange")

    def _clear_log(self):
        self.log_text.delete(1.0, tk.END)
        self._log("日志已清空")

    def _update_ui_connected(self, port_type, baud_rate):
        self.status_label.config(text="已连接", foreground="green")
        self.connect_btn.config(text="断开", command=self._disconnect_device)

        if port_type == 888:
            self.port_var.set("HID")
        elif port_type == 632:
            self.port_var.set("USB")
        elif 0 <= port_type <= 7:
            self.port_var.set(f"COM{port_type + 1}")
        else:
            self.port_var.set(f"端口{port_type}")

        self.baud_var.set(str(baud_rate))

        def read_ver():
            try:
                st, ver = self.mwic.srd_ver(self.detector.status.device_handle, 18)
                if st == 0 and ver:
                    self.root.after(0, lambda: self.hw_ver_label.config(text=ver, foreground="black"))
                else:
                    self.root.after(0, lambda: self.hw_ver_label.config(text=f"错误({st})", foreground="orange"))
            except Exception:
                pass

        threading.Thread(target=read_ver, daemon=True).start()
        self.fw_ver_label.config(text="MWIC_32 DLL", foreground="black")

        if self.detector.status.card_present:
            self.card_status_label.config(text="有卡", foreground="green")
            if self.detector.status.card_type:
                self.card_type_label.config(
                    text=self.detector.status.card_type.name, foreground="blue"
                )
        else:
            self.card_status_label.config(text="无卡", foreground="gray")

    def _connect_device(self):
        if self.detector.status.connected:
            self._log("读写器已连接，无需重复连接")
            return
        try:
            port_str = self.port_var.get()
            if port_str == "USB":
                port_type = AutoCardDetector.PORT_USB
            elif port_str == "HID":
                port_type = AutoCardDetector.PORT_HID
            else:
                port_num = int(port_str.replace("COM", ""))
                port_type = port_num - 1

            baud_rate = int(self.baud_var.get())
            self._log(f"正在连接 {port_str} @ {baud_rate}...")

            if self.detector.connect(port_type, baud_rate):
                self._log("读写器连接成功", "SUCCESS")
                self._update_ui_connected(port_type, baud_rate)
                self._start_detection()
            else:
                self.status_label.config(text="连接失败", foreground="red")
                self._log("读写器连接失败", "ERROR")
                messagebox.showerror("连接错误", "无法连接读写器，请检查端口和波特率设置")
        except Exception as e:
            self._log(f"连接错误：{e}", "ERROR")
            messagebox.showerror("连接错误", str(e))

    def _disconnect_device(self):
        try:
            if self.is_detecting:
                self._stop_detection()
            self._close_all_editors()
            self.detector.disconnect()
            self.status_label.config(text="未连接", foreground="red")
            self.connect_btn.config(text="连接", command=self._connect_device)
            self._log("读写器已断开连接")
            self.hw_ver_label.config(text="-", foreground="gray")
            self.fw_ver_label.config(text="-", foreground="gray")
            self.card_status_label.config(text="无卡", foreground="gray")
            self.card_type_label.config(text="-")
            self.snr_label.config(text="-")
            self.ver_label.config(text="-")
        except Exception as e:
            self._log(f"断开连接错误：{e}", "ERROR")

    def _start_detection(self):
        if not self.detector.status.connected:
            messagebox.showwarning("警告", "请先连接读写器")
            return
        if self.is_detecting:
            return
        self.is_detecting = True
        self.auto_detect_btn.config(text="停止自动检测", command=self._stop_detection)
        self._log("开始自动卡片检测...")
        self.detector.start_auto_detect(self._on_card_event)
        self.status_var.set("自动检测中...")

    def _stop_detection(self):
        if not self.is_detecting:
            return
        self.is_detecting = False
        self.auto_detect_btn.config(text="开始自动检测", command=self._start_detection)
        self._log("停止自动检测")
        self.detector.stop_auto_detect()
        self.status_var.set("就绪")

    def _manual_detect(self):
        if not self.detector.status.connected:
            messagebox.showwarning("警告", "请先连接读写器")
            return

        def detect_thread():
            try:
                self.root.after(0, lambda: self._log("正在检测卡片..."))
                has_card = self.detector._check_card()
                if has_card:
                    self.root.after(0, lambda: self._log("检测到卡片", "SUCCESS"))
                    card_type = self.detector._identify_card()
                    if card_type:
                        self.detector._read_card_info()
                        self.root.after(0, self._update_card_info)
                else:
                    self.root.after(0, lambda: self._log("未检测到卡片", "WARNING"))
                self.root.after(0, lambda: self.status_var.set("就绪"))
            except Exception as e:
                self.root.after(0, lambda: self._log(f"检测错误：{e}", "ERROR"))

        self.status_var.set("检测中...")
        thread = threading.Thread(target=detect_thread, daemon=True)
        thread.start()

    def _read_card_info(self):
        if not self.detector.status.connected:
            messagebox.showwarning("警告", "请先连接读写器")
            return
        if not self.detector.status.card_present:
            messagebox.showinfo("提示", "未检测到卡片")
            return

        def read_thread():
            try:
                self.root.after(0, lambda: self._log("正在读取卡片信息..."))
                self.detector._read_card_info()
                self.root.after(0, self._update_card_info)
                self.root.after(0, lambda: self._log("卡片信息读取成功", "SUCCESS"))
            except Exception as e:
                self.root.after(0, lambda: self._log(f"读取错误：{e}", "ERROR"))

        thread = threading.Thread(target=read_thread, daemon=True)
        thread.start()

    def _read_card_data(self):
        if not self.detector.status.connected:
            messagebox.showwarning("警告", "请先连接读写器")
            return
        if not self.detector.status.card_present:
            messagebox.showinfo("提示", "未检测到卡片")
            return

        def read_data_thread():
            try:
                self.root.after(0, lambda: self._log("正在读取卡片全部数据..."))
                self.root.after(0, lambda: self.status_var.set("读取中..."))

                card_result = self.detector.read_card_full_data()

                if card_result.success:
                    display_text = card_result.get_hex_display()
                    self.root.after(0, lambda: self._log(f"\n{display_text}", "SUCCESS"))

                    mem_info = card_result.memory_info
                    if mem_info:
                        total = mem_info.total_bytes
                        main_len = len(card_result.main_data)
                        pro_len = len(card_result.protection_data)
                        sec_len = len(card_result.security_data)
                        summary = f"读取完成: 主存储器 {main_len}/{total} 字节"
                        if pro_len > 0:
                            summary += f", 保护位 {pro_len} 字节"
                        if sec_len > 0:
                            summary += f", 安全存储器 {sec_len} 字节"
                        self.root.after(0, lambda: self._log(summary, "SUCCESS"))

                    self.root.after(0, lambda: self._open_card_editor(card_result))
                else:
                    self.root.after(0, lambda: self._log(f"读取卡片数据失败: {card_result.error_message}", "ERROR"))

                self.root.after(0, lambda: self.status_var.set("就绪"))
            except Exception as e:
                self.root.after(0, lambda: self._log(f"读取数据错误：{e}", "ERROR"))
                self.root.after(0, lambda: self.status_var.set("就绪"))

        thread = threading.Thread(target=read_data_thread, daemon=True)
        thread.start()

    def _open_card_editor(self, card_data: CardFullData):
        try:
            editor = CardDataEditor(self.root, self.detector, card_data, log_callback=self._log)
            self._editor_windows.append(editor)
            editor.bind('<Destroy>', lambda e: self._on_editor_destroyed(editor))
            editor.focus_set()
        except Exception as e:
            self._log(f"打开编辑器失败：{e}", "ERROR")

    def _on_editor_destroyed(self, editor):
        if editor in self._editor_windows:
            self._editor_windows.remove(editor)

    def _close_all_editors(self):
        for editor in self._editor_windows[:]:
            try:
                if editor.winfo_exists():
                    editor.force_close()
            except tk.TclError:
                pass
        self._editor_windows.clear()

    def _beep_test(self):
        if not self.detector.status.connected:
            messagebox.showwarning("警告", "请先连接读写器")
            return

        def beep_thread():
            try:
                self.root.after(0, lambda: self._log("蜂鸣器测试中..."))
                result = self.mwic.dv_beep(self.detector.status.device_handle, 30)
                if result == IC_OK:
                    self.root.after(0, lambda: self._log("蜂鸣器测试成功", "SUCCESS"))
                else:
                    self.root.after(0, lambda: self._log(f"蜂鸣器测试失败 (返回值: {result})", "ERROR"))
            except Exception as e:
                self.root.after(0, lambda: self._log(f"蜂鸣器测试错误：{e}", "ERROR"))

        thread = threading.Thread(target=beep_thread, daemon=True)
        thread.start()

    def _auto_search_port(self):
        self._log("正在自动搜索读写器...")
        self.status_var.set("搜索中...")

        def search_thread():
            found = self.detector.auto_search_port()
            if found:
                status = self.detector.get_status()
                port_type = status.port_type
                baud_rate = status.baud_rate
                self.root.after(0, self._on_search_success, port_type, baud_rate)
            else:
                self.root.after(0, self._on_search_fail)

        thread = threading.Thread(target=search_thread, daemon=True)
        thread.start()

    def _on_search_success(self, port_type, baud_rate):
        self._log("找到读写器", "SUCCESS")
        self._log("读写器连接成功", "SUCCESS")
        self._update_ui_connected(port_type, baud_rate)
        self._update_card_info()
        self._start_detection()
        self.status_var.set("自动检测中...")

    def _on_search_fail(self):
        self._log("未找到读写器", "WARNING")
        self.status_var.set("就绪")

    def _on_card_event(self, event_type: str, data):
        def update():
            if event_type == "card_detected":
                self._log(f"检测到卡片：{data['type']}", "SUCCESS")
                card_type = self.detector.status.card_type
                if card_type:
                    mem_info = get_card_memory_info(card_type)
                    if mem_info and mem_info.description:
                        self._log(f"卡片信息：{mem_info.description}")
                self._update_card_info()
            elif event_type == "card_removed":
                self._log("卡片已移除", "WARNING")
                self._close_all_editors()
                self.card_status_label.config(text="无卡", foreground="gray")
                self.card_type_label.config(text="-")
                self.snr_label.config(text="-")
                self.ver_label.config(text="-")
            elif event_type == "card_status":
                if data:
                    self.card_status_label.config(text="有卡", foreground="green")
                else:
                    self.card_status_label.config(text="无卡", foreground="gray")
        self.root.after(0, update)

    def _update_card_info(self):
        try:
            status = self.detector.get_status()
            if status.card_present:
                self.card_status_label.config(text="有卡", foreground="green")
                if status.card_type:
                    self.card_type_label.config(text=status.card_type.name, foreground="blue")
                if status.card_snr:
                    self.snr_label.config(text=status.card_snr.upper(), foreground="black")
                if status.card_ver:
                    self.ver_label.config(text=status.card_ver, foreground="black")
            else:
                self.card_status_label.config(text="无卡", foreground="gray")
                self.card_type_label.config(text="-")
                self.snr_label.config(text="-")
                self.ver_label.config(text="-")
        except Exception as e:
            self._log(f"更新卡片信息错误：{e}", "ERROR")

    def _show_about(self):
        about_text = """
卡片自动探测器
版本：2.0.0

通过 32 位 Python 子进程桥接 MWIC_32.dll
支持 HID/USB/串口通信
支持 Mifare/EEPROM/SLE4442/AT24C 等卡片
        """
        messagebox.showinfo("关于", about_text.strip())

    def _on_closing(self):
        if self.is_detecting:
            self._stop_detection()
        if self.detector.status.connected:
            self._disconnect_device()
        self.mwic._stop_bridge()
        self.root.quit()


def main():
    root = tk.Tk()
    app = CardDetectorGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
