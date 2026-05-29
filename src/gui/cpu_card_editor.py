"""
CPU 卡 APDU 命令交互编辑器
支持卡片复位、协议选择、APDU 命令发送与响应解析
"""

import tkinter as tk
from tkinter import ttk, messagebox
import threading
from src.core.constants import IC_OK, IC_ERR


class CpuCardEditor(tk.Toplevel):

    QUICK_COMMANDS = {
        "Select MF": "00A40000023F00",
        "Select DF": "00A4010002",
        "Read Binary": "00B00000",
        "Get Challenge": "0084000008",
        "Verify PIN": "00200000",
        "External Auth": "00820000",
        "Internal Auth": "00880000",
        "Get Response": "00C00000",
        "Update Binary": "00D60000",
    }

    RESP_SW_DESC = {
        "9000": "成功",
        "6100": "SW2=剩余字节数",
        "6200": "状态不变",
        "6281": "数据可能损坏",
        "6282": "文件结尾",
        "6283": "选择的文件无效",
        "6284": "FCI 格式不符合 P2",
        "6300": "验证失败",
        "63Cx": "验证失败，剩余 x 次",
        "6400": "状态不变",
        "6500": "状态改变",
        "6581": "内存错误",
        "6700": "长度错误",
        "6800": "CLA 不支持",
        "6881": "逻辑通道不支持",
        "6882": "安全报文不支持",
        "6900": "不允许的命令",
        "6981": "命令与文件结构不兼容",
        "6982": "安全状态不满足",
        "6983": "验证方法被锁定",
        "6984": "引用数据无效",
        "6985": "使用条件不满足",
        "6986": "不允许(无当前 EF)",
        "6987": "安全报文数据对象丢失",
        "6988": "安全报文数据对象错误",
        "6A00": "P1/P2 错误",
        "6A80": "数据域参数错误",
        "6A81": "功能不支持",
        "6A82": "文件未找到",
        "6A83": "记录未找到",
        "6A84": "内存不足",
        "6A86": "P1/P2 错误",
        "6A87": "Lc 与 P1/P2 不一致",
        "6A88": "引用数据未找到",
        "6B00": "P1/P2 超出范围",
        "6C00": "长度错误(Le)",
        "6D00": "INS 不支持",
        "6E00": "CLA 不支持",
        "6F00": "未知错误",
    }

    def __init__(self, parent, detector, log_callback=None):
        super().__init__(parent)
        self.detector = detector
        self.log_callback = log_callback
        self._atr_data = b""
        self._protocol = 0
        self._history = []

        self.title("CPU 卡 APDU 命令编辑器")
        self.geometry("950x700")

        self._create_widgets()

        self.protocol("WM_DELETE_WINDOW", self.destroy)

        self.after(200, self._cpu_reset)

    def _create_widgets(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        top_frame = ttk.Frame(self, padding="5")
        top_frame.grid(row=0, column=0, sticky=(tk.W, tk.E))

        ttk.Label(top_frame, text="CPU 卡", font=("", 10, "bold")).pack(side=tk.LEFT, padx=5)

        ttk.Label(top_frame, text="协议:").pack(side=tk.LEFT, padx=(15, 3))
        self.protocol_var = tk.StringVar(value="T=0")
        protocol_cb = ttk.Combobox(top_frame, textvariable=self.protocol_var,
                                   values=["T=0", "T=1"], state="readonly", width=5)
        protocol_cb.pack(side=tk.LEFT)
        protocol_cb.bind("<<ComboboxSelected>>", self._on_protocol_changed)

        self.atr_var = tk.StringVar(value="ATR: 未获取")
        atr_label = ttk.Label(top_frame, textvariable=self.atr_var, foreground="gray")
        atr_label.pack(side=tk.LEFT, padx=15)

        ttk.Button(top_frame, text="复位卡片", command=self._cpu_reset,
                   width=10).pack(side=tk.RIGHT, padx=3)

        cmd_frame = ttk.LabelFrame(self, text="APDU 命令", padding="5")
        cmd_frame.grid(row=1, column=0, sticky=(tk.W, tk.E), padx=5, pady=(5, 0))

        row0 = ttk.Frame(cmd_frame)
        row0.pack(fill=tk.X, pady=2)

        ttk.Label(row0, text="CLA:").pack(side=tk.LEFT)
        self.cla_var = tk.StringVar(value="00")
        ttk.Entry(row0, textvariable=self.cla_var, width=5, font=("Consolas", 11)).pack(side=tk.LEFT, padx=(2, 6))

        ttk.Label(row0, text="INS:").pack(side=tk.LEFT)
        self.ins_var = tk.StringVar(value="A4")
        ttk.Entry(row0, textvariable=self.ins_var, width=5, font=("Consolas", 11)).pack(side=tk.LEFT, padx=(2, 6))

        ttk.Label(row0, text="P1:").pack(side=tk.LEFT)
        self.p1_var = tk.StringVar(value="00")
        ttk.Entry(row0, textvariable=self.p1_var, width=5, font=("Consolas", 11)).pack(side=tk.LEFT, padx=(2, 6))

        ttk.Label(row0, text="P2:").pack(side=tk.LEFT)
        self.p2_var = tk.StringVar(value="00")
        ttk.Entry(row0, textvariable=self.p2_var, width=5, font=("Consolas", 11)).pack(side=tk.LEFT, padx=(2, 6))

        ttk.Label(row0, text="Lc:").pack(side=tk.LEFT, padx=(6, 2))
        self.lc_var = tk.StringVar(value="")
        ttk.Entry(row0, textvariable=self.lc_var, width=5, font=("Consolas", 11),
                  state="readonly").pack(side=tk.LEFT, padx=(2, 6))

        ttk.Label(row0, text="Le:").pack(side=tk.LEFT)
        self.le_var = tk.StringVar(value="")
        ttk.Entry(row0, textvariable=self.le_var, width=5, font=("Consolas", 11)).pack(side=tk.LEFT, padx=(2, 6))

        ttk.Button(row0, text="发送命令", command=self._send_command,
                   width=10).pack(side=tk.RIGHT, padx=5)

        row1 = ttk.Frame(cmd_frame)
        row1.pack(fill=tk.X, pady=2)

        ttk.Label(row1, text="数据域:").pack(side=tk.LEFT)
        self.data_var = tk.StringVar(value="")
        data_entry = ttk.Entry(row1, textvariable=self.data_var, font=("Consolas", 11))
        data_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(2, 0))
        data_entry.bind("<KeyRelease>", self._on_data_changed)

        quick_frame = ttk.Frame(cmd_frame)
        quick_frame.pack(fill=tk.X, pady=(5, 0))

        ttk.Label(quick_frame, text="快捷命令:").pack(side=tk.LEFT, padx=(0, 5))
        for name, apdu in self.QUICK_COMMANDS.items():
            ttk.Button(quick_frame, text=name, command=lambda a=apdu: self._fill_apdu(a),
                       width=12).pack(side=tk.LEFT, padx=1)

        resp_frame = ttk.LabelFrame(self, text="响应", padding="5")
        resp_frame.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=(5, 0))
        resp_frame.columnconfigure(0, weight=1)
        resp_frame.rowconfigure(2, weight=1)

        self.sw_var = tk.StringVar(value="SW: --")
        sw_frame = ttk.Frame(resp_frame)
        sw_frame.grid(row=0, column=0, sticky=(tk.W, tk.E))

        ttk.Label(sw_frame, textvariable=self.sw_var, font=("Consolas", 10, "bold"),
                  foreground="green").pack(side=tk.LEFT, padx=5)

        self.sw_desc_var = tk.StringVar(value="")
        ttk.Label(sw_frame, textvariable=self.sw_desc_var, foreground="gray").pack(side=tk.LEFT, padx=10)

        ttk.Separator(resp_frame, orient=tk.HORIZONTAL).grid(row=1, column=0, sticky=(tk.W, tk.E), pady=3)

        self.resp_text = tk.Text(resp_frame, height=6, font=("Consolas", 11),
                                 wrap=tk.NONE, state=tk.DISABLED)
        self.resp_text.grid(row=2, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        resp_scroll = ttk.Scrollbar(resp_frame, orient=tk.VERTICAL, command=self.resp_text.yview)
        resp_scroll.grid(row=2, column=1, sticky=(tk.N, tk.S))
        self.resp_text.configure(yscrollcommand=resp_scroll.set)

        hist_frame = ttk.LabelFrame(self, text="命令历史", padding="5")
        hist_frame.grid(row=3, column=0, sticky=(tk.W, tk.E, tk.N, tk.S), padx=5, pady=5)
        hist_frame.columnconfigure(0, weight=1)
        hist_frame.rowconfigure(0, weight=1)

        self.hist_text = tk.Text(hist_frame, height=5, font=("Consolas", 10),
                                 wrap=tk.NONE, state=tk.DISABLED, bg="#F5F5F5")
        self.hist_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        hist_scroll = ttk.Scrollbar(hist_frame, orient=tk.VERTICAL, command=self.hist_text.yview)
        hist_scroll.grid(row=0, column=1, sticky=(tk.N, tk.S))
        self.hist_text.configure(yscrollcommand=hist_scroll.set)

    def _cpu_reset(self):
        def run():
            self._log("正在复位 CPU 卡...")
            handle = self.detector.status.device_handle
            if handle <= 0:
                self.after(0, lambda: self._show_error("设备未连接"))
                return
            st, atr = self.detector.mwic.cpu_reset(handle)
            if st == IC_OK and atr:
                self._atr_data = atr
                self.after(0, lambda: self._on_reset_ok(atr))
            else:
                self.after(0, lambda: self._show_error(f"复位失败 (返回: {st})"))

        threading.Thread(target=run, daemon=True).start()

    def _on_reset_ok(self, atr: bytes):
        self.atr_var.set(f"ATR: {atr.hex().upper()}")
        self._log(f"卡片复位成功, ATR={atr.hex().upper()}", "SUCCESS")

    def _on_protocol_changed(self, event=None):
        protocol = 0 if self.protocol_var.get() == "T=0" else 1
        handle = self.detector.status.device_handle
        if handle <= 0:
            return

        def run():
            st = self.detector.mwic.cpu_protocol(handle, protocol)
            if st == IC_OK:
                self._protocol = protocol
                self.after(0, lambda: self._log(f"协议切换为 T={'0' if protocol == 0 else '1'}", "SUCCESS"))
            else:
                self.after(0, lambda: self._show_error(f"协议切换失败 (返回: {st})"))

        threading.Thread(target=run, daemon=True).start()

    def _on_data_changed(self, event=None):
        data_text = self._sanitize_hex(self.data_var.get())
        if data_text:
            self.lc_var.set(f"{len(data_text) // 2:02X}")
        else:
            self.lc_var.set("")

    def _fill_apdu(self, apdu_hex: str):
        apdu_hex = apdu_hex.upper()
        self.cla_var.set(apdu_hex[:2])
        self.ins_var.set(apdu_hex[2:4])
        self.p1_var.set(apdu_hex[4:6])
        self.p2_var.set(apdu_hex[6:8])
        if len(apdu_hex) > 10:
            lc_hex = apdu_hex[8:10]
            lc_val = int(lc_hex, 16)
            self.data_var.set(apdu_hex[10:10 + lc_val * 2])
            self.lc_var.set(lc_hex)
            if len(apdu_hex) > 10 + lc_val * 2:
                self.le_var.set(apdu_hex[10 + lc_val * 2:])
            else:
                self.le_var.set("")
        elif len(apdu_hex) > 8:
            self.le_var.set(apdu_hex[8:])
            self.data_var.set("")
        else:
            self.data_var.set("")
            self.lc_var.set("")
            self.le_var.set("")

    def _build_apdu(self) -> bytes:
        header = self.cla_var.get() + self.ins_var.get() + self.p1_var.get() + self.p2_var.get()
        data_text = self._sanitize_hex(self.data_var.get())
        le_text = self._sanitize_hex(self.le_var.get())

        if not data_text and not le_text:
            return bytes.fromhex(header)
        elif data_text and not le_text:
            lc = f"{len(data_text) // 2:02X}"
            return bytes.fromhex(header + lc + data_text)
        elif not data_text and le_text:
            return bytes.fromhex(header + le_text)
        else:
            lc = f"{len(data_text) // 2:02X}"
            return bytes.fromhex(header + lc + data_text + le_text)

    def _send_command(self):
        apdu = self._build_apdu()
        if not apdu:
            return

        handle = self.detector.status.device_handle
        if handle <= 0:
            self._show_error("设备未连接")
            return

        apdu_hex = apdu.hex().upper()
        self._add_history(f"> {apdu_hex}", "send")

        def run():
            st, resp = self.detector.mwic.cpu_comres(handle, apdu)
            if st == IC_OK and resp:
                self.after(0, lambda: self._on_response(resp, apdu_hex))
            else:
                self.after(0, lambda: self._on_response_error(st))

        threading.Thread(target=run, daemon=True).start()

    def _on_response(self, resp: bytes, cmd_hex: str):
        resp_hex = resp.hex().upper()
        sw = ""
        sw_desc = ""
        if len(resp) >= 2:
            sw = f"{resp[-2]:02X}{resp[-1]:02X}"
            self.sw_var.set(f"SW: {sw}")
            sw_desc = self.RESP_SW_DESC.get(sw, "")
            if not sw_desc and sw.startswith("6C"):
                sw_desc = f"长度错误(应为 {int(sw[2:], 16)})"
            elif not sw_desc and sw.startswith("63C"):
                sw_desc = f"验证失败，剩余 {int(sw[3:], 16)} 次"
            self.sw_desc_var.set(f"  ({sw_desc})" if sw_desc else "")
            self.sw_var.set(f"SW: {sw}")

        data_part = resp[:-2] if len(resp) >= 2 else resp
        self.resp_text.config(state=tk.NORMAL)
        self.resp_text.delete("1.0", tk.END)
        if data_part:
            self.resp_text.insert(tk.END, self._format_hex(data_part))
        else:
            self.resp_text.insert(tk.END, "(无数据)")
        self.resp_text.config(state=tk.DISABLED)

        self._add_history(f"< {sw} ({sw_desc})" if sw_desc else f"< {sw}",
                          "ok" if sw == "9000" else "warn")
        self._log(f"APDU {cmd_hex} -> SW={sw}")

    def _on_response_error(self, st):
        self.sw_var.set(f"SW: 错误({st})")
        self.sw_desc_var.set("")
        self.resp_text.config(state=tk.NORMAL)
        self.resp_text.delete("1.0", tk.END)
        self.resp_text.insert(tk.END, f"命令发送失败 (返回值: {st})")
        self.resp_text.config(state=tk.DISABLED)
        self._add_history(f"< 错误({st})", "err")

    def _add_history(self, text: str, tag: str = ""):
        self.hist_text.config(state=tk.NORMAL)
        self.hist_text.insert(tk.END, text + "\n")
        if tag:
            if tag == "ok":
                self.hist_text.tag_add("ok", f"end-2l", f"end-1c")
            elif tag == "err":
                self.hist_text.tag_add("err", f"end-2l", f"end-1c")
            elif tag == "warn":
                self.hist_text.tag_add("warn", f"end-2l", f"end-1c")
        self.hist_text.see(tk.END)
        self.hist_text.config(state=tk.DISABLED)

        self.hist_text.tag_config("ok", foreground="green")
        self.hist_text.tag_config("err", foreground="red")
        self.hist_text.tag_config("warn", foreground="#CC6600")
        self.hist_text.tag_config("send", foreground="#0066CC")

        self._history.append(text)

    def _show_error(self, msg: str):
        self._log(msg, "ERROR")
        messagebox.showerror("错误", msg, parent=self)

    def _sanitize_hex(self, text: str) -> str:
        return "".join(c for c in text.upper() if c in "0123456789ABCDEF")

    def _format_hex(self, data: bytes) -> str:
        lines = []
        for i in range(0, len(data), 16):
            chunk = data[i:i + 16]
            hex_str = " ".join(f"{b:02X}" for b in chunk)
            ascii_str = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
            lines.append(f"{i:04X}  {hex_str:<48s}  {ascii_str}")
        return "\n".join(lines)

    def _log(self, msg: str, level: str = "INFO"):
        if self.log_callback:
            self.log_callback(msg, level)

    def force_close(self):
        self.destroy()