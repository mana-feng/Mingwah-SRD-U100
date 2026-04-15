#!/usr/bin/env python3
"""
MWIC Python 包主入口
卡片自动探测程序
"""

import sys
import argparse
from pathlib import Path


def run_gui():
    """运行 GUI 版本"""
    from src.gui.app import CardDetectorGUI
    import tkinter as tk
    
    root = tk.Tk()
    app = CardDetectorGUI(root)
    root.mainloop()


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="MWIC 卡片自动探测程序",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python main.py              # 运行 GUI 版本（默认）
  python main.py --cli        # 运行命令行版本
  python main.py --version    # 显示版本信息
        """
    )
    
    parser.add_argument(
        "--cli", 
        action="store_true",
        help="运行命令行版本"
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version="MWIC Python 1.0.0"
    )
    
    args = parser.parse_args()
    
    if args.cli:
        from src.core.mwic import MWIC32
        from src.core.detector import AutoCardDetector
        from src.core.types import CardType, get_card_memory_info
        import time
        
        print("=" * 60)
        print("卡片自动探测演示程序")
        print("=" * 60)
        
        mwic = MWIC32()
        print("✓ MWIC32 初始化成功")
        
        detector = AutoCardDetector(mwic)
        
        print("\n正在搜索读写器...")
        if detector.auto_search_port():
            status = detector.get_status()
            print(f"✓ 读写器已连接")
            print(f"  端口类型：{status.port_type}")
            print(f"  波特率：{status.baud_rate}")
        else:
            print("✗ 未找到可用的读写器")
            print("请检查读写器是否正确连接")
            return
        
        def demo_callback(event_type, data):
            print(f"[事件] {event_type}: {data}")
        
        print("\n启动自动卡片检测...")
        print("将卡片放置在读写器上，按 Ctrl+C 退出")
        print("命令: r=读取全部数据, i=读取卡片信息, q=退出\n")
        
        detector.start_auto_detect(demo_callback)
        
        try:
            while True:
                time.sleep(0.1)
                status = detector.get_status()
                if status.card_present:
                    card_desc = ""
                    if status.card_type:
                        mem_info = get_card_memory_info(status.card_type)
                        if mem_info and mem_info.description:
                            card_desc = f" ({mem_info.description})"
                    print(f"\r当前状态：有卡 | 类型：{status.card_type.name if status.card_type else '未知':15} | "
                          f"序列号：{status.card_snr[:16] if status.card_snr else 'N/A':16}{card_desc}", 
                          end='', flush=True)
                else:
                    print(f"\r当前状态：无卡                                  ", 
                          end='', flush=True)
        except KeyboardInterrupt:
            print("\n\n正在停止...")
        finally:
            detector.stop_auto_detect()
            detector.disconnect()
            print("✓ 程序已退出")
    else:
        run_gui()


if __name__ == "__main__":
    main()
