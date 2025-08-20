import tkinter as tk
from tkinter import ttk
import requests
import json
import sounddevice as sd
import numpy as np
import speech_recognition as sr
import time
import sys
import threading
from PIL import Image, ImageTk, ImageDraw, ImageFont
import cv2  # Import OpenCV
import os

# --- VOICEVOX関連の設定 ---
host = "127.0.0.1"
port = "50021"
speaker = 8  # 話者を指定 (例: 8 つむぎ)

def post_audio_query(text: str) -> dict | None:
    """音声合成用のクエリを作成する"""
    params = {"text": text, "speaker": speaker}
    try:
        res = requests.post(
            f"http://{host}:{port}/audio_query",
            params=params,
            timeout=10  # タイムアウト設定
        )
        res.raise_for_status()  # エラーがあれば例外を発生
        return res.json()
    except requests.exceptions.RequestException as e:
        print(f"\nAudio Queryエラー: {e}")
        return None

def post_synthesis(query_data: dict) -> bytes | None:
    """音声合成を実行する"""
    params = {"speaker": speaker}
    headers = {"content-type": "application/json"}
    try:
        res = requests.post(
            f"http://{host}:{port}/synthesis",
            data=json.dumps(query_data),
            params=params,
            headers=headers,
            timeout=20  # タイムアウト設定 (合成は時間がかかる場合がある)
        )
        res.raise_for_status()
        return res.content
    except requests.exceptions.RequestException as e:
        print(f"\nSynthesisエラー: {e}")
        return None

def play_wavfile(wav_data: bytes | None):
    """音声を再生する"""
    if wav_data is None:
        return
    try:
        sample_rate = 24000  # VOICEVOXのデフォルトサンプリングレート
        wav_array = np.frombuffer(wav_data, dtype=np.int16)
        sd.play(wav_array, sample_rate)
        sd.wait()  # 再生が終わるまで待つ
    except Exception as e:
        print(f"\n音声再生エラー: {e}")
        print("利用可能なオーディオデバイスを確認してください。")

# --- 音声認識関連の関数 ---
def recognize_speech_from_mic(recognizer: sr.Recognizer, microphone: sr.Microphone) -> dict:
    """マイクから音声を取得し、テキストに変換する"""
    if not isinstance(recognizer, sr.Recognizer):
        raise TypeError("`recognizer` must be `Recognizer` instance")
    if not isinstance(microphone, sr.Microphone):
        raise TypeError("`microphone` must be `Microphone` instance")

    response = {
        "success": True,
        "error": None,
        "transcription": None
    }

    with microphone as source:
        print("\nマイクのノイズレベルを調整中...")
        try:
            # 実際の音声入力の直前にノイズ調整を行う
            recognizer.adjust_for_ambient_noise(source, duration=1)  # 1秒間調整
            print("どうぞ話してください（2-3秒間）...")
            # タイムアウトとフレーズ制限を短くして応答性を向上
            audio = recognizer.listen(source, timeout=3, phrase_time_limit=3)
        except sr.WaitTimeoutError:
            response["success"] = False
            response["error"] = "タイムアウトしました。音声が検出されませんでした。"
            return response
        except Exception as e:
            response["success"] = False
            response["error"] = f"マイクからの音声取得中にエラー: {e}"
            return response

    try:
        response["transcription"] = recognizer.recognize_google(audio, language='ja-JP')
    except sr.RequestError as e:
        response["success"] = False
        response["error"] = f"Google APIに接続できませんでした; {e}"
    except sr.UnknownValueError:
        response["error"] = "音声を認識できませんでした"
    except Exception as e:
        response["success"] = False
        response["error"] = f"音声認識中に予期せぬエラー: {e}"

    return response

# --- 応答生成関数 (シンプルな応答ロジック) ---
def generate_response(user_text: str | None) -> str:
    """ユーザーの発言に対する応答を生成する"""
    if user_text:
        if "こんにちは" in user_text:
            return "こんにちは！何かお手伝いしましょうか？"
        elif "ありがとう" in user_text or "どうも" in user_text:
            return "どういたしまして！"
        elif "天気" in user_text:
            return "今日の天気はどうでしょうか？外を見てみてくださいね！"
        elif "名前" in user_text:
            return "私はVOICEVOXの連携するAIアシスタントで、声はつむぎが担当しています。"
        elif "何ができる" in user_text:
            return "簡単な日常会話や、特定の質問に答えることができますよ。"
        elif "大きく" in user_text:
            return "ウィンドウを大きくしますね。"
        elif "小さく" in user_text:
            return "ウィンドウを小さくしますね。"
        elif "スライドショー開始" in user_text or "動画開始" in user_text: # 新しい音声コマンド
            return "動画を開始しますね。"
        elif "スライドショー停止" in user_text or "動画停止" in user_text: # 新しい音声コマンド
            return "動画を停止しますね。"
        elif "次のスライド" in user_text or "次の動画" in user_text: # 新しい音声コマンド (動画の場合、次の動画にスキップ)
            return "次の動画に切り替えます。"
        elif "さようなら" in user_text or "バイバイ" in user_text:
            return "はい、さようなら。またお話ししましょう。"
        else:
            return f"「{user_text}」ですね、承知しました。"
    else:
        return "すみません、うまく聞き取れませんでした。もう一度お願いします。"

class VoiceChatApp:
    def __init__(self, master):
        self.master = master  # ルートウィンドウへの参照を保存
        master.title("音声チャット")
        master.geometry("950x1080")  # 初期サイズを調整

        self.base_path = os.path.dirname(os.path.abspath(__file__))  # スクリプトの実行ディレクトリを取得 (絶対パス)

        background_width = 950  #幅
        background_height = 600  #高さ
        try:
            bg_image_path = os.path.join(self.base_path, "frame.jpg")  # 相対パスを結合
            self.bg_image = Image.open(bg_image_path)  # 背景画像のパスを指定
            resized_image = self.bg_image.resize((background_width, background_height), Image.Resampling.LANCZOS)
            self.bg_photo = ImageTk.PhotoImage(resized_image)
            self.bg_label = tk.Label(master, image=self.bg_photo)
            self.bg_label.place(x=0, y=0)
            self.bg_label.lower()  # 他のウィジェットを前面に表示
        except FileNotFoundError:
            print(f"背景画像ファイル '{bg_image_path}' が見つかりません。")
        except Exception as e:
            print(f"背景画像の読み込みまたは設定中にエラーが発生しました: {e}")

        self.vroid_image_original = None  # オリジナルのVRoidキャラクター画像を保持
        self.vroid_photo = None
        self.vroid_label = tk.Label(master)
        self.vroid_label.pack(pady=10)

        try:
            vroid_char_path = os.path.join(self.base_path, "vroid_character.png")  # 相対パスを結合
            self.vroid_image_original = Image.open(vroid_char_path)  # VRoidキャラクターの画像パスを指定
            self.resize_vroid_image()  # 初期表示
        except FileNotFoundError:
            print(f"VRoidキャラクターの画像ファイル '{vroid_char_path}' が見つかりません。")
        except Exception as e:
            print(f"VRoidキャラクター画像の読み込みまたは設定中にエラーが発生しました: {e}")

        # 音声合成中に表示する動画用 (VRoidキャラクターの代わり)
        self.speaking_video_path = os.path.join(self.base_path, "video1.mp4")  # 動画ファイルのパス
        self.cap = None   # OpenCV VideoCaptureオブジェクト
        self.is_video_playing_vroid = False # VRoid動画の再生状態
        self.video_frame_delay = 30   # 動画のフレームレートに応じた遅延 (milliseconds)
        self.video_update_id = None

        self.chat_log = tk.Text(master, height=10, width=50, state=tk.DISABLED)
        self.chat_log.pack(pady=10)

        self.input_frame = ttk.Frame(master, width=400)
        self.input_frame.pack(fill=tk.X, padx=5, pady=5, expand=False)

        self.input_entry = ttk.Entry(self.input_frame)
        self.input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.input_entry.bind("<Return>", self.send_message)

        self.send_button = ttk.Button(self.input_frame, text="送信", command=self.send_message)
        self.send_button.pack(side=tk.RIGHT, padx=5)

        self.button_frame = ttk.Frame(master)
        self.button_frame.pack(pady=5)

        # アイコンをロードし、参照を保持する
        self.icons = {}
        icon_size = (24, 24)  # アイコンの推奨サイズ

        # start_icon.png
        try:
            start_icon_path = os.path.join(self.base_path, "start_icon.png")
            start_img = Image.open(start_icon_path).resize(icon_size, Image.Resampling.LANCZOS)
            self.icons["start"] = ImageTk.PhotoImage(start_img)
            self.start_button = ttk.Button(self.button_frame, text="音声会話を開始", image=self.icons["start"], compound=tk.LEFT, command=self.start_conversation)
        except FileNotFoundError:
            print(f"アイコンファイル '{start_icon_path}' が見つかりません。テキストのみのボタンを使用します。")
            self.start_button = ttk.Button(self.button_frame, text="音声会話を開始", command=self.start_conversation)
        self.start_button.pack(side=tk.LEFT, padx=5)

        # stop_icon.png
        try:
            stop_icon_path = os.path.join(self.base_path, "stop_icon.png")
            stop_img = Image.open(stop_icon_path).resize(icon_size, Image.Resampling.LANCZOS)
            self.icons["stop"] = ImageTk.PhotoImage(stop_img)
            self.stop_button = ttk.Button(self.button_frame, text="終了", image=self.icons["stop"], compound=tk.LEFT, command=self.close_window)
        except FileNotFoundError:
            print(f"アイコンファイル '{stop_icon_path}' が見つかりません。テキストのみのボタンを使用します。")
            self.stop_button = ttk.Button(self.button_frame, text="終了", command=self.close_window)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        self.stop_button.config(state=tk.DISABLED)

        # force_stop_icon.png
        try:
            force_stop_icon_path = os.path.join(self.base_path, "force_stop_icon.png")
            force_stop_img = Image.open(force_stop_icon_path).resize(icon_size, Image.Resampling.LANCZOS)
            self.icons["force_stop"] = ImageTk.PhotoImage(force_stop_img)
            self.force_stop_button = ttk.Button(self.button_frame, text="強制終了", image=self.icons["force_stop"], compound=tk.LEFT, command=self.force_stop_conversation)
        except FileNotFoundError:
            print(f"アイコンファイル '{force_stop_icon_path}' が見つかりません。テキストのみのボタンを使用します。")
            self.force_stop_button = ttk.Button(self.button_frame, text="強制終了", command=self.force_stop_conversation)
        self.force_stop_button.pack(side=tk.LEFT, padx=5)
        self.force_stop_button.config(state=tk.DISABLED)

        # --- 動画スライドショー制御ボタンを追加 ---
        self.slideshow_button_frame = ttk.Frame(master)
        self.slideshow_button_frame.pack(pady=5)

        # play_video_icon.png
        try:
            play_video_icon_path = os.path.join(self.base_path, "play_video_icon.png") # 仮のアイコン名
            play_video_img = Image.open(play_video_icon_path).resize(icon_size, Image.Resampling.LANCZOS)
            self.icons["play_video"] = ImageTk.PhotoImage(play_video_img)
            self.start_slideshow_button = ttk.Button(self.slideshow_button_frame, text="動画再生開始", image=self.icons["play_video"], compound=tk.LEFT, command=self.start_video_slideshow)
        except FileNotFoundError:
            print(f"アイコンファイル '{play_video_icon_path}' が見つかりません。テキストのみのボタンを使用します。")
            self.start_slideshow_button = ttk.Button(self.slideshow_button_frame, text="動画再生開始", command=self.start_video_slideshow)
        self.start_slideshow_button.pack(side=tk.LEFT, padx=5)

        # stop_video_icon.png
        try:
            stop_video_icon_path = os.path.join(self.base_path, "stop_video_icon.png") # 仮のアイコン名
            stop_video_img = Image.open(stop_video_icon_path).resize(icon_size, Image.Resampling.LANCZOS)
            self.icons["stop_video"] = ImageTk.PhotoImage(stop_video_img)
            self.stop_slideshow_button = ttk.Button(self.slideshow_button_frame, text="動画再生停止", image=self.icons["stop_video"], compound=tk.LEFT, command=self.stop_video_slideshow)
        except FileNotFoundError:
            print(f"アイコンファイル '{stop_video_icon_path}' が見つかりません。テキストのみのボタンを使用します。")
            self.stop_slideshow_button = ttk.Button(self.slideshow_button_frame, text="動画再生停止", command=self.stop_video_slideshow)
        self.stop_slideshow_button.pack(side=tk.LEFT, padx=5)
        self.stop_slideshow_button.config(state=tk.DISABLED)

        # next_video_icon.png (もし複数の動画を切り替える場合)
        try:
            next_video_icon_path = os.path.join(self.base_path, "next_video_icon.png") # 仮のアイコン名
            next_video_img = Image.open(next_video_icon_path).resize(icon_size, Image.Resampling.LANCZOS)
            self.icons["next_video"] = ImageTk.PhotoImage(next_video_img)
            self.next_slide_button = ttk.Button(self.slideshow_button_frame, text="次の動画", image=self.icons["next_video"], compound=tk.LEFT, command=self.next_video)
        except FileNotFoundError:
            print(f"アイコンファイル '{next_video_icon_path}' が見つかりません。テキストのみのボタンを使用します。")
            self.next_slide_button = ttk.Button(self.slideshow_button_frame, text="次の動画", command=self.next_video)
        self.next_slide_button.pack(side=tk.LEFT, padx=5)


        self.recognizer = sr.Recognizer()
        self.microphone = None  # 初期値をNoneに設定

        self.initialize_microphone()  # マイクの初期化を別途関数に切り出す

        self.is_talking = False
        self.conversation_thread = None

        master.bind("<Configure>", self.on_resize)

        # --- 動画スライドショー表示用の設定 ---
        self.video_slideshow_label = tk.Label(master)
        # スライドショー画像をロードする代わりに、動画ファイルのリストを保持
        self.video_files = []
        self.current_video_index = 0
        self.current_video_cap = None # 現在再生中の動画のVideoCaptureオブジェクト
        self.is_video_slideshow_playing = False # 動画スライドショーの再生状態
        self.video_slideshow_after_id = None

        # 動画フォルダのパスを、スクリプトからの相対パスに変更
        videos_folder_name = "videos"
        videos_folder_path = os.path.join(self.base_path, videos_folder_name)
        self.load_video_files(videos_folder_path)

    def initialize_microphone(self):
        """マイクの初期化を試みる"""
        try:
            mic_names = sr.Microphone.list_microphone_names()
            if not mic_names:
                self.update_chat_log("エラー: 利用可能なマイクデバイスが見つかりませんでした。", "red")
                print("エラー: 利用可能なマイクデバイスが見つかりませんでした。マイクが接続されているか、OSの設定を確認してください。", file=sys.stderr)
                self.start_button.config(state=tk.DISABLED)
                return

            print("検出されたマイクデバイス:")
            for i, name in enumerate(mic_names):
                print(f"  {i}: {name}")

            self.microphone = sr.Microphone()
            self.update_chat_log("マイクの準備ができました。", "green")
            self.start_button.config(state=tk.NORMAL)

        except Exception as e:
            self.update_chat_log(f"エラー: マイクの初期化に失敗しました: {e}\nマイクが接続され、OSでアクセス許可されているか確認してください。", "red")
            print(f"マイクの初期化に失敗しました: {e}", file=sys.stderr)
            print("マイクが接続され、OSでアクセス許可されているか確認してください。", file=sys.stderr)
            self.microphone = None
            self.start_button.config(state=tk.DISABLED)

    def get_video_files(self, folder_path):
        """指定されたフォルダ内の動画ファイルを取得する"""
        video_extensions = ('.mp4', '.avi', '.mov', '.mkv', '.webm')
        files = []
        if not os.path.isdir(folder_path):
            print(f"エラー: 指定された動画フォルダが見つかりません: {folder_path}")
            return []

        for f in os.listdir(folder_path):
            if f.lower().endswith(video_extensions):
                files.append(os.path.join(folder_path, f))
        files.sort()
        return files

    def load_video_files(self, video_folder_path):
        """動画スライドショー用の動画ファイルを読み込む"""
        self.video_files = []
        files = self.get_video_files(video_folder_path)

        if not files:
            print(f"指定された動画フォルダ '{video_folder_path}' に動画ファイルが見つかりませんでした。")
            # フォルダが存在しない場合は作成し、ダミー動画生成を促すメッセージ
            if not os.path.exists(video_folder_path):
                os.makedirs(video_folder_path)
                print(f"'{video_folder_path}' フォルダを作成しました。ここにMP4ファイルを配置してください。")
            self.update_chat_log(f"エラー: '{video_folder_path}' フォルダに動画ファイルが見つかりません。MP4ファイルを配置してください。", "red")
        else:
            self.video_files.extend(files)
            print(f"ロードされた動画ファイル: {self.video_files}")


    def update_video_frame(self):
        """動画のフレームを読み込み、表示する"""
        if self.is_video_slideshow_playing and self.current_video_cap and self.current_video_cap.isOpened():
            ret, frame = self.current_video_cap.read()
            if ret:
                try:
                    # OpenCVのBGR形式からPILのRGB形式へ変換
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    pil_image = Image.fromarray(frame_rgb)

                    # ラベルの現在のサイズを取得 (表示されていない場合は0になるのでデフォルトサイズを設定)
                    label_width = self.video_slideshow_label.winfo_width()
                    label_height = self.video_slideshow_label.winfo_height()

                    if label_width < 10 or label_height < 10:
                        window_width = self.master.winfo_width()
                        window_height = self.master.winfo_height()
                        label_width = max(int(window_width * 0.7), 600) # スライドショー領域の目安
                        label_height = max(int(window_height * 0.4), 400) # スライドショー領域の目安

                    # 画像のアスペクト比を維持しつつ、ラベルに収まるようにリサイズ
                    original_width, original_height = pil_image.size
                    if original_width > 0 and original_height > 0 and label_width > 0 and label_height > 0:
                        ratio_w = label_width / original_width
                        ratio_h = label_height / original_height
                        ratio = min(ratio_w, ratio_h)
                    else:
                        ratio = 1 # 無効なサイズの場合はリサイズしない

                    new_width = int(original_width * ratio)
                    new_height = int(original_height * ratio)

                    if new_width == 0: new_width = 1
                    if new_height == 0: new_height = 1

                    resized_image = pil_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    tk_image = ImageTk.PhotoImage(resized_image)
                    self.video_slideshow_label.config(image=tk_image)
                    self.video_slideshow_label.image = tk_image # ガベージコレクションを防ぐための参照保持

                except Exception as e:
                    print(f"動画フレームの処理または表示中にエラー: {e}")
                    self.stop_video_slideshow() # エラーが発生したら停止
                    return
            else:
                # 動画の終わりに達したら、次の動画へ、またはループ
                if len(self.video_files) > 1:
                    self.next_video()
                else:
                    # 1つの動画しかない場合はループ再生
                    self.current_video_cap.set(cv2.CAP_PROP_POS_FRAMES, 0) # フレームを最初に戻す

            # 次のフレームを更新
            if self.is_video_slideshow_playing:
                self.video_slideshow_after_id = self.master.after(self.video_frame_delay, self.update_video_frame)
        else:
            # 動画再生が停止したら、ラベルをクリア
            self.video_slideshow_label.config(image='')
            self.video_slideshow_label.image = None


    def start_video_slideshow(self):
        """動画スライドショーの再生を開始する"""
        if not self.video_files:
            self.update_chat_log("動画スライドショーに表示する動画ファイルがありません。", "orange")
            return

        if not self.is_video_slideshow_playing:
            self.is_video_slideshow_playing = True
            self.video_slideshow_label.pack(pady=10, expand=True, fill=tk.BOTH) # ここで表示

            # 最初の動画をロード
            self.current_video_index = 0
            self.current_video_cap = cv2.VideoCapture(self.video_files[self.current_video_index])

            if not self.current_video_cap.isOpened():
                self.update_chat_log(f"エラー: 動画ファイル '{self.video_files[self.current_video_index]}' を開けませんでした。", "red")
                self.stop_video_slideshow()
                return

            # フレームレートから適切な遅延を計算
            fps = self.current_video_cap.get(cv2.CAP_PROP_FPS)
            if fps > 0:
                self.video_frame_delay = int(1000 / fps)
            else:
                self.video_frame_delay = 30 # デフォルト値

            self.update_chat_log(f"動画スライドショーを開始します: {os.path.basename(self.video_files[self.current_video_index])}", "green")
            self.start_slideshow_button.config(text="動画再生中", state=tk.DISABLED)
            self.stop_slideshow_button.config(state=tk.NORMAL)
            self.next_slide_button.config(state=tk.NORMAL) # 次の動画ボタンも有効化

            self.update_video_frame() # 最初のフレームを表示し、ループを開始


    def stop_video_slideshow(self):
        """動画スライドショーの再生を停止する"""
        if self.is_video_slideshow_playing:
            self.is_video_slideshow_playing = False
            if self.video_slideshow_after_id:
                self.master.after_cancel(self.video_slideshow_after_id)
                self.video_slideshow_after_id = None
            if self.current_video_cap:
                self.current_video_cap.release() # 動画キャプチャを解放
                self.current_video_cap = None
            self.video_slideshow_label.pack_forget() # ラベルを非表示にする
            self.video_slideshow_label.config(image='')
            self.video_slideshow_label.image = None # ガベージコレクション対策
            self.update_chat_log("動画スライドショーを停止しました。", "orange")
            self.start_slideshow_button.config(text="動画再生開始", state=tk.NORMAL)
            self.stop_slideshow_button.config(state=tk.DISABLED)
            # self.next_slide_button.config(state=tk.DISABLED) # 必要に応じて無効化

    def next_video(self):
        """次の動画に切り替える"""
        if not self.video_files:
            return

        if self.current_video_cap:
            self.current_video_cap.release() # 現在の動画キャプチャを解放

        self.current_video_index = (self.current_video_index + 1) % len(self.video_files)
        new_video_path = self.video_files[self.current_video_index]

        self.current_video_cap = cv2.VideoCapture(new_video_path)
        if not self.current_video_cap.isOpened():
            self.update_chat_log(f"エラー: 次の動画ファイル '{os.path.basename(new_video_path)}' を開けませんでした。", "red")
            self.stop_video_slideshow()
            return

        # 新しい動画のFPSを再計算
        fps = self.current_video_cap.get(cv2.CAP_PROP_FPS)
        if fps > 0:
            self.video_frame_delay = int(1000 / fps)
        else:
            self.video_frame_delay = 30 # デフォルト値

        self.update_chat_log(f"次の動画に切り替えます: {os.path.basename(new_video_path)}", "green")
        # 既存のafterをキャンセルし、新しい動画の表示を開始
        if self.video_slideshow_after_id:
            self.master.after_cancel(self.video_slideshow_after_id)
        self.update_video_frame()


    def resize_vroid_image(self, width=None, height=None):
        """通常のVRoid画像をリサイズして表示する"""
        if self.vroid_image_original:
            if width is None or height is None:
                window_width = self.master.winfo_width()
                window_height = self.master.winfo_height()
                width = int(window_width * 0.4)
                height = int(window_height * 0.3)

            if width <= 0: width = 1
            if height <= 0: height = 1

            original_width, original_height = self.vroid_image_original.size
            if original_width == 0 or original_height == 0:
                print("元のVRoid画像サイズが無効です。")
                return

            ratio_w = width / original_width
            ratio_h = height / original_height
            ratio = min(ratio_w, ratio_h)

            new_width = int(original_width * ratio)
            new_height = int(original_height * ratio)

            if new_width <= 0: new_width = 1
            if new_height <= 0: new_height = 1

            try:
                resized_image = self.vroid_image_original.resize((new_width, new_height), Image.Resampling.LANCZOS)
                self.vroid_photo = ImageTk.PhotoImage(resized_image)
                self.vroid_label.config(image=self.vroid_photo)
            except Exception as e:
                print(f"VRoid画像のリサイズ中にエラー: {e}")

    def _start_speaking_animation(self):
        """VRoidキャラクターの speaking_video を再生する"""
        if not self.is_video_playing_vroid:
            self.cap = cv2.VideoCapture(self.speaking_video_path)
            if not self.cap.isOpened():
                self.update_chat_log(f"エラー: speaking_video ファイル '{self.speaking_video_path}' を開けませんでした。", "red")
                return

            fps = self.cap.get(cv2.CAP_PROP_FPS)
            if fps > 0:
                self.video_frame_delay = int(1000 / fps)
            else:
                self.video_frame_delay = 30

            self.is_video_playing_vroid = True
            self._play_speaking_animation_video()

    def _play_speaking_animation_video(self):
        """動画のフレームを定期的に更新して表示する"""
        if self.is_talking and self.cap and self.cap.isOpened() and self.is_video_playing_vroid:
            ret, frame = self.cap.read()
            if ret:
                try:
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    pil_image = Image.fromarray(frame_rgb)

                    window_width = self.master.winfo_width()
                    window_height = self.master.winfo_height()
                    target_width = int(window_width * 0.4)
                    target_height = int(window_height * 0.3)
                    if target_width <= 0: target_width = 100
                    if target_height <= 0: target_height = 100

                    original_width, original_height = pil_image.size
                    ratio_w = target_width / original_width
                    ratio_h = target_height / original_height
                    ratio = min(ratio_w, ratio_h)
                    new_width = int(original_width * ratio)
                    new_height = int(original_height * ratio)
                    if new_width <= 0: new_width = 1
                    if new_height <= 0: new_height = 1

                    resized_image = pil_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    self.speaking_vroid_photo = ImageTk.PhotoImage(resized_image)
                    self.vroid_label.config(image=self.speaking_vroid_photo)
                except Exception as e:
                    print(f"動画フレームの処理または表示中にエラー: {e}")
            else:
                print("VRoid speaking_video の終わりに達しました。最初から再生します。")
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0) # フレームを最初に戻す

            self.video_update_id = self.master.after(self.video_frame_delay, self._play_speaking_animation_video)
        elif self.is_talking:
            self.update_chat_log("エラー: VRoid speaking_video ファイルを開けませんでした。", "red")
            self._end_speaking_animation()


    def _end_speaking_animation(self):
        """VRoidキャラクターの speaking_video の再生を停止し、通常画像に戻す"""
        if self.is_video_playing_vroid:
            self.is_video_playing_vroid = False
            if self.video_update_id:
                self.master.after_cancel(self.video_update_id)
                self.video_update_id = None
            if self.cap:
                self.cap.release()
                self.cap = None
            self.resize_vroid_image() # 通常画像に戻す

    def on_resize(self, event):
        # ウィンドウサイズ変更時に、VRoidとスライドショーの両方を調整
        if not self.is_talking: # 会話中でなければ通常のVRoid画像をリサイズ
            self.resize_vroid_image(event.width, int(event.height * 0.3)) # ウィンドウの新しい幅と高さを使用
        else:
            # 会話中は動画が表示されているが、ここでは特に何もしない。
            # _start_speaking_animationで適切なサイズに調整されるため。
            pass

        # 動画スライドショーのラベルサイズを現在のウィンドウサイズに合わせて調整
        if self.is_video_slideshow_playing: # または self.video_slideshow_label.winfo_ismapped():
            self.update_video_frame() # update_video_frame内でリサイズロジックが実行される


    def send_message(self, event=None):
        message = self.input_entry.get()
        if message:
            self.update_chat_log(f"あなた: {message}")
            self.input_entry.delete(0, tk.END)
            response_text = generate_response(message)
            self.update_chat_log(f"AI: {response_text}", "blue")
            self.speak(response_text) # 非同期で実行されるspeak関数を呼び出す

    def start_conversation(self):
        if self.microphone is None:
            self.update_chat_log("エラー: マイクが使用できません。アプリケーションを再起動し、マイクが接続され、許可されていることを確認してください。", "red")
            return

        if not self.is_talking:
            self.is_talking = True
            self.start_button.config(state=tk.DISABLED)
            self.stop_button.config(state=tk.NORMAL)
            self.force_stop_button.config(state=tk.NORMAL)
            self.update_chat_log("会話を開始します。話しかけてください。", "green")

            # 会話開始時にVRoid Speaking動画の再生を開始
            self._start_speaking_animation()

            self.conversation_thread = threading.Thread(target=self.conversation_loop_gui)
            self.conversation_thread.start()

    def conversation_loop_gui(self):
        if not self.is_talking:
            self._end_speaking_animation() # 会話が停止されたらすぐにアニメーションを終了
            return

        self.update_chat_log("-" * 20)
        speech_response = recognize_speech_from_mic(self.recognizer, self.microphone)

        user_input = None
        if speech_response["success"]:
            user_input = speech_response["transcription"]
            if user_input:
                self.update_chat_log(f"あなた (音声): 「{user_input}」")
            elif speech_response["error"]: # 音声は検出されたが認識できなかった場合
                self.update_chat_log(f"音声認識: {speech_response['error']}", "red")
                response_text = generate_response(None) # 聞き取れなかった場合の応答
                self.update_chat_log(f"AI: {response_text}", "blue")
                self.speak(response_text)
        elif not speech_response["success"]: # 音声自体が検出されなかったり、マイクエラーの場合
            self.update_chat_log(f"音声認識エラー: {speech_response['error']}", "red")
            self.speak("すみません、音声の認識で問題がありました。")


        if user_input: # user_inputがNoneでない場合のみ応答を生成・発話
            # スライドショー関連の音声コマンドを処理
            if "動画開始" in user_input or "スライドショー開始" in user_input:
                self.start_video_slideshow()
                response_text = "動画を開始しますね。"
            elif "動画停止" in user_input or "スライドショー停止" in user_input:
                self.stop_video_slideshow()
                response_text = "動画を停止しますね。"
            elif "次の動画" in user_input or "次のスライド" in user_input:
                self.next_video()
                response_text = "次の動画に切り替えます。"
            elif "さようなら" in user_input or "バイバイ" in user_input:
                response_text = "はい、さようなら。またお話ししましょう。"
                self.update_chat_log(f"AI: {response_text}", "blue")
                self.speak(response_text)
                self.stop_conversation()
                return # 会話を終了するので、それ以上進まない
            else:
                response_text = generate_response(user_input)

            self.update_chat_log(f"AI: {response_text}", "blue")
            self.speak(response_text)


        # 会話を続けるために再度音声認識を開始 (ただし、is_talkingがTrueの場合のみ)
        if self.is_talking:
            self.master.after(100, self.conversation_loop_gui) # 0.1秒後に再度実行

    def stop_conversation(self):
        if self.is_talking:
            self.is_talking = False
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
            self.force_stop_button.config(state=tk.DISABLED)
            self.update_chat_log("会話を終了します。", "red")
            self._end_speaking_animation() # 会話終了時にアニメーションも終了

    def force_stop_conversation(self):
        if self.is_talking:
            self.is_talking = False
            self.start_button.config(state=tk.NORMAL)
            self.stop_button.config(state=tk.DISABLED)
            self.force_stop_button.config(state=tk.DISABLED)
            self.update_chat_log("会話を強制終了します。", "purple")  # 強制終了を目立たせる
            self._end_speaking_animation()  # 強制終了時にアニメーションも終了

    def update_chat_log(self, message, color="black"):
        self.chat_log.config(state=tk.NORMAL)
        self.chat_log.insert(tk.END, message + "\n", color)
        self.chat_log.config(state=tk.DISABLED)
        self.chat_log.see(tk.END)  # 最新のメッセージを表示
        self.chat_log.tag_config("red", foreground="red")
        self.chat_log.tag_config("blue", foreground="blue")
        self.chat_log.tag_config("green", foreground="green")
        self.chat_log.tag_config("purple", foreground="purple")  # 強制終了用の色
        self.chat_log.tag_config("orange", foreground="orange")


    def close_window(self):
        """ウィンドウを閉じる"""
        self.stop_video_slideshow() # ウィンドウを閉じるときに動画スライドショーを停止
        self._end_speaking_animation() # VRoid Speaking動画も停止
        self.master.destroy()

    def speak(self, text: str):
        """テキストをVOICEVOXで音声化して再生するヘルパー関数（非同期で実行）"""
        # 発話が始まる前に、VRoid Speaking動画アニメーションを開始
        self.master.after(0, self._start_speaking_animation)
        self.master.after(0, lambda: self.update_chat_log("AI [発話中]..."))

        query_data = post_audio_query(text)
        if query_data:
            wav_data = post_synthesis(query_data)
            if wav_data:
                play_wavfile(wav_data)
            else:
                self.update_chat_log("音声合成に失敗しました。", "red")
        else:
            self.update_chat_log("音声クエリの作成に失敗しました。", "red")

        # 発話が終了したら、VRoid Speaking動画アニメーションを停止し、通常画像に戻す
        self.master.after(0, self._end_speaking_animation)
        # 会話を続けるためのループを再度呼び出す
        if self.is_talking:
            self.master.after(100, self.conversation_loop_gui)


if __name__ == "__main__":
    root = tk.Tk()
    app = VoiceChatApp(root)
    root.mainloop()
