import os
import queue
import ffmpeg
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from concurrent.futures import ThreadPoolExecutor
from tkinterdnd2 import TkinterDnD, DND_FILES
import urllib.parse  # 新增导入用于解析URI

if getattr(sys, 'frozen', False):
    base_dir = sys._MEIPASS
else:
    base_dir = os.path.dirname(os.path.abspath(__file__))

icon_path = os.path.join(base_dir, "icon.ico")

class VideoCompressorApp(TkinterDnD.Tk):
    def __init__(self):
        super().__init__()
        self.title("视频压缩工具 V2.0.0")
        self.geometry("1200x800")
        self.iconbitmap(icon_path)
        
        # 设置现代主题
        self.style = ttk.Style(self)
        self.style.theme_use('clam')
        self.configure_style()
        
        # 初始化拖放功能
        self.drop_target_register(DND_FILES)
        self.dnd_bind('<<Drop>>', self.on_drop)
        
        # 任务队列和状态跟踪
        self.task_queue = queue.Queue()
        self.status_dict = {}
        self.running = True
        self.executor = None
        
        self.create_widgets()
        self.after(100, self.update_status)

    def all_tasks_completed(self):
        """检查所有任务是否处于完成状态"""
        for item in self.status_dict.values():
            if item["status"] not in ("完成", "失败", "错误"):
                return False
        return True
    def configure_style(self):
        # 自定义颜色方案
        self.style.configure('.', background='#F5F5F5', foreground='#333')
        self.style.map('TButton',
            background=[('active', '#4A90E2'), ('disabled', '#BDBDBD')],
            foreground=[('active', 'white'), ('disabled', '#757575')]
        )
        self.style.configure('TButton', padding=6, relief='flat', 
                           background='#2196F3', foreground='white')
        self.style.configure('Header.TFrame', background='#2196F3')
        self.style.configure('Status.Treeview', rowheight=30)
        self.style.map('Treeview',
            background=[('selected', '#E3F2FD')],
            foreground=[('selected', '#000')]
        )
        self.style.configure('TProgressbar', thickness=20, troughcolor='#EEE',
                            background='#4CAF50', lightcolor='#4CAF50', darkcolor='#388E3C')

    def create_widgets(self):
        # 顶部标题栏
        header_frame = ttk.Frame(self, style='Header.TFrame')
        header_frame.pack(fill=tk.X, padx=0, pady=0)
        ttk.Label(header_frame, text="视频压缩工具", font=('Helvetica', 16, 'bold'), 
                 foreground='white', background='#2196F3').pack(pady=15)

        # 主内容区域
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(10, 20))

        # 文件操作区域
        file_btn_frame = ttk.Frame(main_frame)
        file_btn_frame.pack(fill=tk.X, pady=(0, 10))
        
        self.btn_select = ttk.Button(file_btn_frame, text="+ 添加文件", 
                                   command=self.add_files, style='TButton')
        self.btn_select.pack(side=tk.LEFT, padx=5)
        
        self.btn_clear = ttk.Button(file_btn_frame, text="清空列表", 
                                  command=self.clear_files, style='TButton')
        self.btn_clear.pack(side=tk.LEFT, padx=5)
        
        # 文件列表
        file_list_frame = ttk.LabelFrame(main_frame, text=" 待处理文件列表 ", 
                                       padding=10)
        file_list_frame.pack(fill=tk.BOTH, expand=True)
        
        self.file_list = ttk.Treeview(file_list_frame, columns=("name", "status", "original_size", "compressed_size"), 
                                    show="headings", style='Status.Treeview')
        vsb = ttk.Scrollbar(file_list_frame, orient="vertical", command=self.file_list.yview)
        hsb = ttk.Scrollbar(file_list_frame, orient="horizontal", command=self.file_list.xview)
        self.file_list.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        
        self.file_list.heading("name", text="文件名", anchor=tk.W)
        self.file_list.heading("status", text="状态", anchor=tk.CENTER)
        self.file_list.heading("original_size", text="原大小", anchor=tk.CENTER)
        self.file_list.heading("compressed_size", text="压缩后大小", anchor=tk.CENTER)
        self.file_list.column("name", width=400, anchor=tk.W)
        self.file_list.column("status", width=200, anchor=tk.CENTER)
        self.file_list.column("original_size", width=200, anchor=tk.CENTER)
        self.file_list.column("compressed_size", width=200, anchor=tk.CENTER)
        
        self.file_list.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        file_list_frame.grid_columnconfigure(0, weight=1)
        file_list_frame.grid_rowconfigure(0, weight=1)

        # 设置区域
        settings_frame = ttk.LabelFrame(main_frame, text=" 压缩设置 ", padding=10)
        settings_frame.pack(fill=tk.X, pady=(10, 5))
        
        settings_grid = ttk.Frame(settings_frame)
        settings_grid.pack(fill=tk.X, padx=5)
        
        # 第一行设置
        ttk.Label(settings_grid, text="输出格式:", font=('Segoe UI', 9)).grid(row=0, column=0, padx=10, pady=5, sticky=tk.W)
        self.format_var = tk.StringVar(value="mp4")
        self.format_combo = ttk.Combobox(settings_grid, textvariable=self.format_var, 
                                       values=["mp4", "webm", "mov", "avi", "mkv", "flv", "vob", "m4v", "wmv"], width=8, state="readonly")
        self.format_combo.grid(row=0, column=1, padx=10, sticky=tk.W)
        
        ttk.Label(settings_grid, text="视频质量 (0-51):", font=('Segoe UI', 9)).grid(row=0, column=2, padx=10, sticky=tk.W)
        self.quality_var = tk.IntVar(value=28)
        self.quality_spin = ttk.Spinbox(settings_grid, from_=0, to=51, textvariable=self.quality_var, width=5)
        self.quality_spin.grid(row=0, column=3, padx=10, sticky=tk.W)
        
        self.mute_var = tk.BooleanVar()
        self.mute_check = ttk.Checkbutton(settings_grid, text="静音处理", variable=self.mute_var)
        self.mute_check.grid(row=0, column=4, padx=10, sticky=tk.W)
        
        # 第二行设置
        ttk.Label(settings_grid, text="输出目录:", font=('Segoe UI', 9)).grid(row=1, column=0, padx=10, pady=10, sticky=tk.W)
        self.output_path = tk.StringVar()
        self.output_entry = ttk.Entry(settings_grid, textvariable=self.output_path, width=40)
        self.output_entry.grid(row=1, column=1, columnspan=3, padx=10, sticky=tk.W)
        self.btn_output = ttk.Button(settings_grid, text="浏览...", command=self.select_output, style='TButton')
        self.btn_output.grid(row=1, column=4, padx=10, sticky=tk.W)

        # 控制区域
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=(10, 0))
        
        ttk.Label(control_frame, text="最大并行任务:", font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=5)
        self.parallel_var = tk.IntVar(value=2)
        self.parallel_spin = ttk.Spinbox(control_frame, from_=1, to=8, textvariable=self.parallel_var, width=4)
        self.parallel_spin.pack(side=tk.LEFT, padx=5)
        
        self.btn_start = ttk.Button(control_frame, text="▶ 开始压缩", style='Accent.TButton', command=self.start_processing)
        self.btn_start.pack(side=tk.RIGHT, padx=5)
        
        self.progress = ttk.Progressbar(control_frame, mode="determinate", style='TProgressbar')
        self.progress.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=5)

        # 状态颜色标签
        self.style.configure('Status.Waiting', background='#BDBDBD', foreground='#333')
        self.style.configure('Status.Processing', background='#2196F3', foreground='white')
        self.style.configure('Status.Success', background='#4CAF50', foreground='white')
        self.style.configure('Status.Error', background='#F44336', foreground='white')

        # 添加自定义样式
        self.style.configure('Accent.TButton', background='#4CAF50', foreground='white')
        self.style.map('Accent.TButton',
            background=[('active', '#45a049'), ('disabled', '#BDBDBD')]
        )

    def on_drop(self, event):
        # 解析拖放路径（保持原有代码不变）
        files = []
        raw_paths = []
        
        if isinstance(event.data, str):
            if event.data.startswith('{') and event.data.endswith('}'):
                cleaned = event.data.strip('{}')
                raw_paths = cleaned.split('} {')
            else:
                raw_paths = event.data.split()
        elif isinstance(event.data, list):
            raw_paths = event.data
        
        paths = []
        for path in raw_paths:
            if path.startswith('file://'):
                path = urllib.parse.unquote(path[7:])
                if path.startswith('/') and ':' in path:
                    path = path[1:]
            paths.append(path)

        # 过滤有效视频文件（保持原有代码不变）
        video_extensions = ('.mp4', '.avi', '.mov', '.webm', 
                        '.mkv', '.flv', '.vob', '.m4v')
        for path in paths:
            if os.path.isfile(path):
                ext = os.path.splitext(path)[1].lower()
                if ext in video_extensions:
                    files.append(path)
        
        # 在添加新文件前检查完成状态
        if files and self.all_tasks_completed() and self.status_dict:
            self.clear_files()
        
        # 添加文件到列表（保持原有代码不变）
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
        # 在添加新文件前检查完成状态
        if self.all_tasks_completed() and self.status_dict:
            self.clear_files()
        
        files = filedialog.askopenfilenames(
            filetypes=[("视频文件", "*.mp4;*.avi;*.mov;*.webm;*.mkv;*.flv;*.avi;*.vob;*.m4v")]
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
            
            # 更新状态颜色
            status_tag = ''
            if '完成' in status:
                status_tag = 'Success'
            elif '失败' in status or '错误' in status:
                status_tag = 'Error'
            elif '处理中' in status:
                status_tag = 'Processing'
            else:
                status_tag = 'Waiting'
            
            self.file_list.item(item_id, values=current_values, tags=(status_tag,))
            self.file_list.tag_configure('Success', background='#E8F5E9')
            self.file_list.tag_configure('Error', background='#FFEBEE')
            self.file_list.tag_configure('Processing', background='#E3F2FD')
            self.file_list.tag_configure('Waiting', background='white')
        
        # 更新进度条
        total = len(self.status_dict)
        completed = sum(1 for s in self.status_dict.values() if s["status"] in ("完成", "失败", "错误"))
        if total > 0:
            self.progress["value"] = (completed / total) * 100
        
        # 检查是否全部完成
        if total == completed and total > 0:
            self.progress.stop()
            self.toggle_controls(True)
            if completed == total:
                self.progress["value"] = 100
        
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

        # 检测输入文件的流信息
        probe = ffmpeg.probe(video_path)
        has_video = any(s['codec_type'] == 'video' for s in probe['streams'])
        has_audio = any(s['codec_type'] == 'audio' for s in probe['streams'])

        if not has_video:
            return False, "输入文件不包含视频流"

        input_stream = ffmpeg.input(video_path)
        video_stream = input_stream.video.filter('pad', **{
            'width': 'ceil(iw/2)*2',
            'height': 'ceil(ih/2)*2'
        })

        # 动态构建输出参数
        output_args = {
            'vcodec': 'libvpx-vp9' if convert_to_extension == 'webm' else 'libx264',
            'crf': quality,
            'y': '-y',
            'map_metadata': '-1'  # 移除元数据
        }

        # 显式流映射控制
        output = ffmpeg.output(video_stream, output_file, **output_args)
        output = output.global_args('-map', '0:v:0')  # 强制映射第一个视频流

        # 处理音频逻辑
        if not should_mute_video and has_audio:
            output = output.global_args('-map', '0:a:0?')  # 可选音频映射
            output = output.audio.codec('aac' if convert_to_extension == 'mp4' else 'libvorbis')

        # 处理无音频流时的静音参数
        if should_mute_video or not has_audio:
            output = output.global_args('-an')

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
