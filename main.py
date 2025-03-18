import os
import queue
import ffmpeg
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from concurrent.futures import ThreadPoolExecutor
from tkinterdnd2 import TkinterDnD, DND_FILES

if getattr(sys, 'frozen', False):
    base_dir = sys._MEIPASS
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))

icon_path = os.path.join(base_dir, "icon.ico")

class VideoCompressorApp(TkinterDnD.Tk):
    def __init__(self):
        super().__init__()
        self.title("视频压缩工具")
        self.geometry("1000x600")
        self.iconbitmap(icon_path)
        
        # 初始化拖放功能
        self.drop_target_register(DND_FILES)
        self.dnd_bind('<<Drop>>', self.on_drop)
        
        # 任务队列和状态跟踪
        self.task_queue = queue.Queue()
        self.status_dict = {}
        self.running = True
        self.executor = None
        
        # 创建UI组件
        self.create_widgets()
        
        # 开始状态更新线程
        self.after(100, self.update_status)

    def create_widgets(self):
        # 文件选择区域
        file_frame = ttk.LabelFrame(self, text="文件选择")
        file_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.btn_select = ttk.Button(file_frame, text="添加视频文件", command=self.add_files)
        self.btn_select.pack(side=tk.LEFT, padx=5)
        
        self.btn_clear = ttk.Button(file_frame, text="清空列表", command=self.clear_files)
        self.btn_clear.pack(side=tk.LEFT, padx=5)
        
        # 文件列表
        self.file_list = ttk.Treeview(self, columns=("name", "status", "original_size", "compressed_size"), 
                                    show="headings", height=10)
        self.file_list.heading("name", text="文件名")
        self.file_list.heading("status", text="状态")
        self.file_list.heading("original_size", text="原大小")
        self.file_list.heading("compressed_size", text="压缩后大小")
        self.file_list.column("name", width=300)
        self.file_list.column("status", width=150)
        self.file_list.column("original_size", width=150)
        self.file_list.column("compressed_size", width=150)
        self.file_list.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 参数设置区域
        settings_frame = ttk.LabelFrame(self, text="压缩设置")
        settings_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(settings_frame, text="输出格式:").grid(row=0, column=0, padx=5, sticky=tk.W)
        self.format_var = tk.StringVar(value="mp4")
        self.format_combo = ttk.Combobox(settings_frame, textvariable=self.format_var, 
                                       values=["mp4", "webm", "mov", "avi"], width=8, state="readonly")
        self.format_combo.grid(row=0, column=1, padx=5)
        
        ttk.Label(settings_frame, text="质量 (0-51):").grid(row=0, column=2, padx=5, sticky=tk.W)
        self.quality_var = tk.IntVar(value=28)
        self.quality_spin = ttk.Spinbox(settings_frame, from_=0, to=51, textvariable=self.quality_var, width=5)
        self.quality_spin.grid(row=0, column=3, padx=5)
        
        self.mute_var = tk.BooleanVar()
        self.mute_check = ttk.Checkbutton(settings_frame, text="静音", variable=self.mute_var)
        self.mute_check.grid(row=0, column=4, padx=5)
        
        ttk.Label(settings_frame, text="输出目录:").grid(row=0, column=5, padx=5, sticky=tk.W)
        self.btn_output = ttk.Button(settings_frame, text="选择...", command=self.select_output)
        self.btn_output.grid(row=0, column=6, padx=5)
        self.output_path = tk.StringVar()
        self.output_label = ttk.Label(settings_frame, textvariable=self.output_path)
        self.output_label.grid(row=0, column=7, padx=5)
        
        # 并行控制区域
        control_frame = ttk.Frame(self)
        control_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(control_frame, text="最大并行任务:").pack(side=tk.LEFT, padx=5)
        self.parallel_var = tk.IntVar(value=2)
        self.parallel_spin = ttk.Spinbox(control_frame, from_=1, to=8, textvariable=self.parallel_var, width=4)
        self.parallel_spin.pack(side=tk.LEFT)
        
        self.btn_start = ttk.Button(control_frame, text="开始压缩", command=self.start_processing)
        self.btn_start.pack(side=tk.RIGHT, padx=5)
        
        self.progress = ttk.Progressbar(control_frame, mode="indeterminate")
        self.progress.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=5)

    def on_drop(self, event):
        files = []
        # 处理不同平台拖放路径格式
        raw_paths = event.data.strip('{}').split('} {') if isinstance(event.data, str) else []
        for path in raw_paths:
            if os.path.isfile(path):
                ext = os.path.splitext(path)[1].lower()
                if ext in ('.mp4', '.avi', '.mov', '.webm'):
                    files.append(path)
        for file_path in files:
            original_size = self.get_file_size(file_path)
            item_id = self.file_list.insert("", "end", values=(
                os.path.basename(file_path),
                "等待中",
                original_size,
                ""
            ))
            self.status_dict[item_id] = {
                "path": file_path,
                "status": "等待中",
                "original_size": original_size,
                "compressed_size": ""
            }

    def add_files(self):
        files = filedialog.askopenfilenames(
            filetypes=[("视频文件", "*.mp4;*.avi;*.mov;*.webm")]
        )
        for file_path in files:
            original_size = self.get_file_size(file_path)
            item_id = self.file_list.insert("", "end", values=(
                os.path.basename(file_path),
                "等待中",
                original_size,
                ""
            ))
            self.status_dict[item_id] = {
                "path": file_path,
                "status": "等待中",
                "original_size": original_size,
                "compressed_size": ""
            }

    def clear_files(self):
        for item in self.file_list.get_children():
            self.file_list.delete(item)
        self.status_dict.clear()

    def select_output(self):
        path = filedialog.askdirectory()
        if path:
            self.output_path.set(path)

    def start_processing(self):
        # 禁用所有设置控件
        self.toggle_controls(False)
        
        max_workers = self.parallel_var.get()
        if not self.status_dict:
            messagebox.showwarning("警告", "请先添加要处理的视频文件")
            self.toggle_controls(True)
            return

        self.progress.start()
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        
        for item_id in self.status_dict:
            if self.status_dict[item_id]["status"] == "等待中":
                self.executor.submit(
                    self.process_video,
                    item_id,
                    self.status_dict[item_id]["path"],
                    self.format_var.get(),
                    self.quality_var.get(),
                    self.mute_var.get(),
                    self.output_path.get()
                )

    def toggle_controls(self, enabled):
        state = "normal" if enabled else "disabled"
        self.format_combo.config(state=state)
        self.quality_spin.config(state=state)
        self.mute_check.config(state=state)
        self.btn_output.config(state=state)
        self.parallel_spin.config(state=state)
        self.btn_start.config(state=state)

    def process_video(self, item_id, path, fmt, quality, mute, output_dir):
        self.task_queue.put((item_id, "处理中", ""))
        
        try:
            output_path = self.generate_output_path(path, fmt, output_dir)
            success, message = compress_video(
                path,
                convert_to_extension=fmt,
                quality=quality,
                should_mute_video=mute,
                output_dir=output_dir
            )
            
            if success:
                file_size = self.get_file_size(output_path)
                self.task_queue.put((item_id, "完成", file_size))
            else:
                self.task_queue.put((item_id, f"失败: {message}", ""))
        except Exception as e:
            self.task_queue.put((item_id, f"错误: {str(e)}", ""))

    def get_file_size(self, file_path):
        size = os.path.getsize(file_path)
        return self.convert_size(size)

    def convert_size(self, size_bytes):
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size_bytes < 1024:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024

    def generate_output_path(self, input_path, fmt, output_dir):
        base_name = os.path.basename(input_path)
        file_name = os.path.splitext(base_name)[0] + "_compressed." + fmt
        return os.path.join(output_dir, file_name) if output_dir else \
               os.path.join(os.path.dirname(input_path), file_name)

    def update_status(self):
        while not self.task_queue.empty():
            item_id, status, compressed_size = self.task_queue.get()
            self.status_dict[item_id]["status"] = status
            self.status_dict[item_id]["compressed_size"] = compressed_size
            
            current_values = list(self.file_list.item(item_id, "values"))
            current_values[1] = status
            current_values[3] = compressed_size
            self.file_list.item(item_id, values=current_values)
        
        # 检查所有任务是否完成
        all_done = all(
            status["status"] in ("完成", "失败", "错误") 
            for status in self.status_dict.values()
        )
        
        if all_done:
            self.progress.stop()
            self.toggle_controls(True)
        
        if self.running:
            self.after(100, self.update_status)

    def on_closing(self):
        self.running = False
        if self.executor:
            self.executor.shutdown(wait=False)
        self.destroy()

def compress_video(video_path, convert_to_extension, quality, should_mute_video, output_dir=None):
    try:
        output_file = generate_output_path(video_path, convert_to_extension, output_dir)
        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        input_stream = ffmpeg.input(video_path)
        video_stream = input_stream.video.filter('pad', **{
            'width': 'ceil(iw/2)*2',
            'height': 'ceil(ih/2)*2'
        })
        audio_stream = None if should_mute_video else input_stream.audio

        codec = 'libvpx-vp9' if convert_to_extension == 'webm' else 'libx264'
        output_args = {
            'vcodec': codec,
            'crf': quality,
            'y': '-y'
        }

        if audio_stream:
            output = ffmpeg.output(video_stream, audio_stream, output_file, **output_args)
        else:
            output = ffmpeg.output(video_stream, output_file, **output_args)

        ffmpeg.run(output)
        return True, "压缩成功"
    except ffmpeg.Error as e:
        error_msg = e.stderr.decode() if e.stderr else "未知错误"
        return False, error_msg
    except Exception as e:
        return False, str(e)

def generate_output_path(input_path, fmt, output_dir):
    base_name = os.path.basename(input_path)
    file_name = os.path.splitext(base_name)[0] + "_compressed." + fmt
    return os.path.join(output_dir, file_name) if output_dir else \
           os.path.join(os.path.dirname(input_path), file_name)

if __name__ == "__main__":
    app = VideoCompressorApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()