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
speaker = 8 # 話者を指定 (例: 8 つむぎ)

def post_audio_query(text: str) -> dict | None:
    """音声合成用のクエリを作成する"""
    params = {"text": text, "speaker": speaker}
    try:
        res = requests.post(
            f"http://{host}:{port}/audio_query",
            params=params,
            timeout=10 # タイムアウト設定
        )
        res.raise_for_status() # エラーがあれば例外を発生
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
            timeout=20 # タイムアウト設定 (合成は時間がかかる場合がある)
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
        sample_rate = 24000 # VOICEVOXのデフォルトサンプリングレート
        wav_array = np.frombuffer(wav_data, dtype=np.int16)
        sd.play(wav_array, sample_rate)
        sd.wait() # 再生が終わるまで待つ
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
            recognizer.adjust_for_ambient_noise(source, duration=1) # 1秒間調整
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
        elif "スライドショー開始" in user_text: # 新しい音声コマンド
            return "スライドショーを開始しますね。"
        elif "スライドショー停止" in user_text: # 新しい音声コマンド
            return "スライドショーを停止しますね。"
        elif "次のスライド" in user_text: # 新しい音声コマンド
            return "次のスライドに切り替えます。"
        elif "さようなら" in user_text or "バイバイ" in user_text:
            return "はい、さようなら。またお話ししましょう。"
        else:
            return f"「{user_text}」ですね、承知しました。"
    else:
        return "すみません、うまく聞き取れませんでした。もう一度お願いします。"

class VoiceChatApp:
    def __init__(self, master):
        self.master = master # ルートウィンドウへの参照を保存
        master.title("音声チャット")
        master.geometry("950x1080") # 初期サイズを調整

        self.base_path = os.path.dirname(os.path.abspath(__file__)) # スクリプトの実行ディレクトリを取得 (絶対パス)

        background_width = 950 #幅
        background_height = 600 #高さ
        try:
            bg_image_path = os.path.join(self.base_path, "frame.jpg") # 相対パスを結合
            self.bg_image = Image.open(bg_image_path) # 背景画像のパスを指定
            resized_image = self.bg_image.resize((background_width, background_height), Image.Resampling.LANCZOS)
            self.bg_photo = ImageTk.PhotoImage(resized_image)
            self.bg_label = tk.Label(master, image=self.bg_photo)
            self.bg_label.place(x=0, y=0)
            self.bg_label.lower() # 他のウィジェットを前面に表示
        except FileNotFoundError:
            print(f"背景画像ファイル '{bg_image_path}' が見つかりません。")
        except Exception as e:
            print(f"背景画像の読み込みまたは設定中にエラーが発生しました: {e}")

        self.vroid_image_original = None # オリジナルのVRoidキャラクター画像を保持
        self.vroid_photo = None
        self.vroid_label = tk.Label(master)
        self.vroid_label.pack(pady=10)

        try:
            vroid_char_path = os.path.join(self.base_path, "vroid_character.png") # 相対パスを結合
            self.vroid_image_original = Image.open(vroid_char_path) # VRoidキャラクターの画像パスを指定
            self.resize_vroid_image() # 初期表示
        except FileNotFoundError:
            print(f"VRoidキャラクターの画像ファイル '{vroid_char_path}' が見つかりません。")
        except Exception as e:
            print(f"VRoidキャラクター画像の読み込みまたは設定中にエラーが発生しました: {e}")

        # 音声合成中に表示する動画用
        self.speaking_video_path = os.path.join(self.base_path, "video1.mp4") # 動画ファイルのパス
        self.cap = None  # OpenCV VideoCaptureオブジェクト
        self.is_video_playing = False
        self.video_frame_delay = 30  # 動画のフレームレートに応じた遅延 (milliseconds)
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
        icon_size = (24, 24) # アイコンの推奨サイズ

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

        # スライドショー制御ボタンを追加
        self.slideshow_button_frame = ttk.Frame(master)
        self.slideshow_button_frame.pack(pady=5) # 初期状態から表示

        # start_slideshow_icon.png
        try:
            start_slideshow_icon_path = os.path.join(self.base_path, "start_slideshow_icon.png")
            start_slideshow_img = Image.open(start_slideshow_icon_path).resize(icon_size, Image.Resampling.LANCZOS)
            self.icons["start_slideshow"] = ImageTk.PhotoImage(start_slideshow_img)
            self.start_slideshow_button = ttk.Button(self.slideshow_button_frame, text="スライドショー開始", image=self.icons["start_slideshow"], compound=tk.LEFT, command=self.start_slideshow_playback)
        except FileNotFoundError:
            print(f"アイコンファイル '{start_slideshow_icon_path}' が見つかりません。テキストのみのボタンを使用します。")
            self.start_slideshow_button = ttk.Button(self.slideshow_button_frame, text="スライドショー開始", command=self.start_slideshow_playback)
        self.start_slideshow_button.pack(side=tk.LEFT, padx=5)

        # stop_slideshow_icon.png
        try:
            stop_slideshow_icon_path = os.path.join(self.base_path, "stop_slideshow_icon.png")
            stop_slideshow_img = Image.open(stop_slideshow_icon_path).resize(icon_size, Image.Resampling.LANCZOS)
            self.icons["stop_slideshow"] = ImageTk.PhotoImage(stop_slideshow_img)
            self.stop_slideshow_button = ttk.Button(self.slideshow_button_frame, text="スライドショー停止", image=self.icons["stop_slideshow"], compound=tk.LEFT, command=self.stop_slideshow_playback)
        except FileNotFoundError:
            print(f"アイコンファイル '{stop_slideshow_icon_path}' が見つかりません。テキストのみのボタンを使用します。")
            self.stop_slideshow_button = ttk.Button(self.slideshow_button_frame, text="スライドショー停止", command=self.stop_slideshow_playback)
        self.stop_slideshow_button.pack(side=tk.LEFT, padx=5)
        self.stop_slideshow_button.config(state=tk.DISABLED) # 最初は停止ボタンを無効化

        # next_slide_icon.png
        try:
            next_slide_icon_path = os.path.join(self.base_path, "next_slide_icon.png")
            next_slide_img = Image.open(next_slide_icon_path).resize(icon_size, Image.Resampling.LANCZOS)
            self.icons["next_slide"] = ImageTk.PhotoImage(next_slide_img)
            self.next_slide_button = ttk.Button(self.slideshow_button_frame, text="次のスライド", image=self.icons["next_slide"], compound=tk.LEFT, command=self.next_slide)
        except FileNotFoundError:
            print(f"アイコンファイル '{next_slide_icon_path}' が見つかりません。テキストのみのボタンを使用します。")
            self.next_slide_button = ttk.Button(self.slideshow_button_frame, text="次のスライド", command=self.next_slide)
        self.next_slide_button.pack(side=tk.LEFT, padx=5)

        self.is_slideshow_playing_button = False # ボタンの状態を追跡

        # ボタンへの参照を保存 (アイコン付きボタンに変更したため、更新)
        self.start_button_ref = self.start_button
        self.stop_button_ref = self.stop_button
        self.force_stop_button_ref = self.force_stop_button

        self.recognizer = sr.Recognizer()
        self.microphone = None # 初期値をNoneに設定

        self.initialize_microphone() # マイクの初期化を別途関数に切り出す

        self.is_talking = False
        self.conversation_thread = None

        master.bind("<Configure>", self.on_resize)

        # --- スライドショー表示用の設定 ---
        self.slideshow_label = tk.Label(master)
        self.slideshow_pil_images = [] # PIL.Imageオブジェクトを格納
        self.slideshow_tk_images = [] # ImageTk.PhotoImageオブジェクトを格納 (参照保持用)
        self.current_slide_index = 0
        self.slideshow_interval_ms = 3000 # 3秒ごとに切り替え
        self.slideshow_playing = False
        self.slideshow_after_id = None # after()のIDを保持

        # スライドショー画像フォルダのパスを、スクリプトからの相対パスに変更
        slides_folder_name = "img"
        slides_folder_path = os.path.join(self.base_path, slides_folder_name)
        self.load_slideshow_images(slides_folder_path)

    def initialize_microphone(self):
        """マイクの初期化を試みる"""
        try:
            # 可能なマイクデバイスをリストアップ
            mic_names = sr.Microphone.list_microphone_names()
            if not mic_names:
                self.update_chat_log("エラー: 利用可能なマイクデバイスが見つかりませんでした。", "red")
                print("エラー: 利用可能なマイクデバイスが見つかりませんでした。マイクが接続されているか、OSの設定を確認してください。", file=sys.stderr)
                self.start_button.config(state=tk.DISABLED) # 会話開始ボタンを無効化
                return

            print("検出されたマイクデバイス:")
            for i, name in enumerate(mic_names):
                print(f"  {i}: {name}")

            # デフォルトのマイクを使用するか、特定のデバイスインデックスを指定する
            # 例: self.microphone = sr.Microphone(device_index=1)
            self.microphone = sr.Microphone()
            self.update_chat_log("マイクの準備ができました。", "green")
            self.start_button.config(state=tk.NORMAL) # 成功したらボタンを有効化

        except Exception as e:
            self.update_chat_log(f"エラー: マイクの初期化に失敗しました: {e}\nマイクが接続され、OSでアクセス許可されているか確認してください。", "red")
            print(f"マイクの初期化に失敗しました: {e}", file=sys.stderr)
            print("マイクが接続され、OSでアクセス許可されているか確認してください。", file=sys.stderr)
            self.microphone = None
            self.start_button.config(state=tk.DISABLED) # 失敗したらボタンを無効化

    def get_image_files(self, folder_path):
        """指定されたフォルダ内の画像ファイルを取得する"""
        image_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff')
        files = []
        if not os.path.isdir(folder_path):
            print(f"エラー: 指定された画像フォルダが見つかりません: {folder_path}")
            return []

        for f in os.listdir(folder_path):
            if f.lower().endswith(image_extensions):
                files.append(os.path.join(folder_path, f))
        files.sort() # ファイル名をソートして順番に表示
        return files

    def load_slideshow_images(self, image_folder_path):
        """スライドショー用の画像を読み込む"""
        self.slideshow_pil_images = [] # PIL Imageオブジェクトを格納
        self.slideshow_tk_images = [] # ImageTk.PhotoImageオブジェクトを格納 (参照保持用)
        files = self.get_image_files(image_folder_path)

        if not files:
            print(f"指定されたスライドショーフォルダ '{image_folder_path}' に画像ファイルが見つかりませんでした。")
            # フォルダが存在しない場合は作成し、ダミー画像を生成
            if not os.path.exists(image_folder_path):
                os.makedirs(image_folder_path)
                print(f"'{image_folder_path}' フォルダを作成しました。")
                try:

                    font_path = "arial.ttf" # WindowsのArialフォントパスの例。環境に合わせて調整
                    if sys.platform.startswith('linux'):
                        font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
                    elif sys.platform == 'darwin': # macOS
                        font_path = "/Library/Fonts/Arial.ttf"

                    try:
                        font = ImageFont.truetype(font_path, 30)
                    except IOError:
                        font = ImageFont.load_default() # デフォルトフォントを使用

                    for i in range(3):
                        dummy_image = Image.new('RGB', (400, 300), color = (i*80, i*40, 255 - i*80))
                        d = ImageDraw.Draw(dummy_image)
                        d.text((20,20), f"Slide {i+1}", fill=(255,255,0), font=font)
                        dummy_image.save(os.path.join(image_folder_path, f'slide_{i+1}.png'))
                    print(f"ダミー画像を '{image_folder_path}' に作成しました。")
                    files = self.get_image_files(image_folder_path) # 再度読み込み
                except Exception as e:
                    print(f"ダミー画像の生成中にエラーが発生しました: {e}")

        for img_path in files:
            try:
                self.slideshow_pil_images.append(Image.open(img_path))
            except Exception as e:
                print(f"スライドショー画像 '{img_path}' の読み込み中にエラーが発生しました: {e}")

        if not self.slideshow_pil_images:
            print("スライドショーに表示する画像がありません。")

    def update_slide(self):
        """現在のスライドを表示する"""
        if not self.slideshow_pil_images:
            self.slideshow_label.config(image='')
            self.slideshow_label.image = None # 参照をクリア
            return

        pil_image = self.slideshow_pil_images[self.current_slide_index]

        # ラベルの現在のサイズを取得
        label_width = self.slideshow_label.winfo_width()
        label_height = self.slideshow_label.winfo_height()

        # 初期表示時など、まだサイズが取得できない場合は、親ウィンドウのサイズを基準にする
        if label_width < 10 or label_height < 10: # 小さすぎる値も考慮
            window_width = self.master.winfo_width()
            window_height = self.master.winfo_height()
            # スライドショーの推奨サイズ比率に基づいて計算
            label_width = max(int(window_width * 0.7), 600)
            label_height = max(int(window_height * 0.4), 400)


        # 画像のアスペクト比を維持しつつ、ラベルに収まるようにリサイズ
        original_width, original_height = pil_image.size

        # 幅と高さの比率を計算し、小さい方を選ぶことで画像が収まるようにする
        if original_width > 0 and original_height > 0 and label_width > 0 and label_height > 0: # ゼロ除算回避
            ratio_w = label_width / original_width
            ratio_h = label_height / original_height
            ratio = min(ratio_w, ratio_h)
        else: # 画像サイズが不正な場合
            ratio = 1 # リサイズしない

        new_width = int(original_width * ratio)
        new_height = int(original_height * ratio)

        # リサイズした画像が0にならないように最低限のサイズを保証
        if new_width == 0: new_width = 1
        if new_height == 0: new_height = 1

        try:
            resized_image = pil_image.resize((new_width, new_height), Image.Resampling.LANCZOS)
            tk_image = ImageTk.PhotoImage(resized_image)
            self.slideshow_label.config(image=tk_image)
            self.slideshow_label.image = tk_image # ガベージコレクションを防ぐための参照保持
        except Exception as e:
            print(f"スライドショー画像のリサイズまたは表示中にエラー: {e}")

    def next_slide(self):
        """次のスライドに切り替える"""
        if not self.slideshow_pil_images:
            return
        self.current_slide_index = (self.current_slide_index + 1) % len(self.slideshow_pil_images)
        self.update_slide()

    def start_slideshow_playback(self):
        """スライドショーの再生を開始する"""
        if not self.slideshow_playing and self.slideshow_pil_images:
            # スライドショーのウィジェットを表示する
            self.slideshow_label.pack(pady=10, expand=True, fill=tk.BOTH) # ここで表示

            # 初期サイズを設定して画像を更新 (現在のウィンドウサイズを考慮)
            self.resize_slideshow_label(width=self.master.winfo_width(), height=int(self.master.winfo_height() * 0.4))

            self.slideshow_playing = True
            self.slideshow_button_loop()
            self.start_slideshow_button.config(text="スライドショー実行中", state=tk.DISABLED)
            self.stop_slideshow_button.config(state=tk.NORMAL)
            self.is_slideshow_playing_button = True

    def stop_slideshow_playback(self):
        """スライドショーの再生を停止する"""
        if self.slideshow_playing:
            self.slideshow_playing = False
            if self.slideshow_after_id:
                self.master.after_cancel(self.slideshow_after_id)
            self.start_slideshow_button.config(text="スライドショー開始", state=tk.NORMAL)
            self.stop_slideshow_button.config(state=tk.DISABLED)
            self.is_slideshow_playing_button = False
            # スライドショーのウィジェットを非表示にする
            self.slideshow_label.pack_forget()

    def slideshow_button_loop(self):
        """スライドショーを自動で切り替えるループ"""
        if self.slideshow_playing:
            self.next_slide()
            self.slideshow_after_id = self.master.after(self.slideshow_interval_ms, self.slideshow_button_loop)

    def resize_slideshow_label(self, width, height):
        """スライドショー表示ラベルのサイズを変更する"""
        # ラベルのサイズを設定 (packで配置しているため、width/heightは優先されない場合がある)
        # しかし、update_slideでこのサイズを基準にリサイズするように修正
        # self.slideshow_label.config(width=width, height=height) # 直接設定は pack_forget/pack と競合しやすいため削除
        self.update_slide() # 画像を現在のラベルサイズに合わせて再表示 (winfo_width/heightで実際のサイズを取得する)

    def resize_vroid_image(self, width=None, height=None):
        """通常のVRoid画像をリサイズして表示する"""
        if self.vroid_image_original:
            if width is None or height is None:
                # デフォルトのVRoid画像サイズをウィンドウの高さの約30%に設定
                # ウィンドウの現在のサイズを取得してから計算
                window_width = self.master.winfo_width()
                window_height = self.master.winfo_height()
                width = int(window_width * 0.4) # ウィンドウ幅の約40%
                height = int(window_height * 0.3) # ウィンドウ高さの約30%

            # widthやheightが0にならないようにする
            if width <= 0: width = 1
            if height <= 0: height = 1

            # アスペクト比を維持してリサイズ
            original_width, original_height = self.vroid_image_original.size
            if original_width == 0 or original_height == 0:
                print("元のVRoid画像サイズが無効です。")
                return

            ratio_w = width / original_width
            ratio_h = height / original_height
            ratio = min(ratio_w, ratio_h) # どちらか小さい方に合わせる

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

    def _play_speaking_animation_video(self):
        """動画のフレームを定期的に更新して表示する"""
        if self.is_talking and self.cap and self.cap.isOpened():
            ret, frame = self.cap.read()
            if ret:
                try:
                    # OpenCVのBGR形式からPILのRGB形式へ変換
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    pil_image = Image.fromarray(frame_rgb)

                    # リサイズ処理 (ウィンドウサイズに合わせて)
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
                # 動画の再生が終了したら、ループを停止し、元の画像に戻す
                print("動画の終わりに達しました。最初から再生します。")
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0) # フレームを最初に戻す
                ret, frame = self.cap.read() # 新しいフレームを読み込む
                if ret:
                    try:
                        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                        pil_image = Image.fromarray(frame_rgb)
                        # リサイズ処理を再度適用
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
                        print(f"動画の再開とフレーム処理中にエラー: {e}")
                else:
                    self.update_chat_log("エラー: 動画ファイルを最初から読み込めませんでした。", "red")
                    self._end_speaking_animation()
                    return # これ以上進まない

            self.video_update_id = self.master.after(self.video_frame_delay, self._play_speaking_animation_video)
        elif self.is_talking:
            # 動画がオープンできなかった場合のエラー処理
            self.update_chat_log("エラー: 動画ファイルを開けませんでした。", "red")
            self._end_speaking_animation()


    def on_resize(self, event):
        # ウィンドウサイズ変更時に、VRoidとスライドショーの両方を調整
        if not self.is_talking: # 会話中でなければ通常のVRoid画像をリサイズ
            self.resize_vroid_image(event.width, int(event.height * 0.3)) # ウィンドウの新しい幅と高さを使用
        else:
            # 会話中は動画が表示されているが、ここでは特に何もしない。
            # _start_speaking_animationで適切なサイズに調整されるため。
            pass

        # スライドショーのラベルサイズを現在のウィンドウサイズに合わせて調整 (update_slideで画像も再調整される)
        if self.slideshow_playing or self.slideshow_label.winfo_ismapped(): # 表示されている場合のみ
            self.resize_slideshow_label(event.width, int(event.height * 0.4)) # 例: ウィンドウ高さの40%をスライドショーに割り当てる

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

            # 会話開始時に動画の再生を開始
            self._start_speaking_animation()

            self.conversation_thread = threading.Thread(target=self.conversation_loop_gui)
            self.conversation_thread.start()

    def conversation_loop_gui(self):
        # 会話が停止された場合はループを抜ける
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
            elif speech_response["error"]:
                self.update_chat_log(f"音声認識: {speech_response['error']}", "red")
                response_text = generate_response(None)
                self.update_chat_log(f"AI: {response_text}", "blue")
                self.speak(response_text)
        elif not speech_response["success"]:
            self.update_chat_log(f"音声認識エラー: {speech_response['error']}", "red")
            self.speak("すみません、音声の認識で問題がありました。")

        if user_input and ("さようなら" in user_input or "バイバイ" in user_input):
            response_text = "はい、さようなら。またお話ししましょう。"
            self.update_chat_log(f"AI: {response_text}", "blue")
            self.speak(response_text)
            self.stop_conversation()
            return

        if user_input:
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
            self.update_chat_log("会話を強制終了します。", "purple") # 強制終了を目立たせる
            self._end_speaking_animation() # 強制終了時にアニメーションも終了

    def update_chat_log(self, message, color="black"):
        self.chat_log.config(state=tk.NORMAL)
        self.chat_log.insert(tk.END, message + "\n", color)
        self.chat_log.config(state=tk.DISABLED)
        self.chat_log.see(tk.END) # 最新のメッセージを表示
        self.chat_log.tag_config("red", foreground="red")
        self.chat_log.tag_config("blue", foreground="blue")
        self.chat_log.tag_config("green", foreground="green")
        self.chat_log.tag_config("purple", foreground="purple") # 強制終了用の色

    def close_window(self):
        """ウィンドウを閉じる"""
        self.stop_slideshow_playback() # ウィンドウを閉じるときにスライドショーを停止
        self._end_speaking_animation() # 念のため動画も停止
        self.master.destroy()

    def speak(self, text: str):
        """テキストをVOICEVOXでA音声化して再生するヘルパー関数（非同期で実行）"""
        # GUI更新はメインスレッドで行う
        # 発話が始まる前に、動画アニメーションを開始
        self.master.after(0, self._start_speaking_animation)
        self.master.after(0, lambda: self.update_chat_log("AI [発話中]..."))

        # 音声合成と再生は別スレッドで実行
        def actual_speak_process():
            # ウィンドウサイズ変更コマンドの処理は、音声合成前に実行
            if "大きく" in text:
                self.master.after(0, lambda: self.master.geometry("700x600"))
            elif "小さく" in text:
                self.master.after(0, lambda: self.master.geometry("500x400"))
            elif "スライドショー開始" in text:
                self.master.after(0, self.start_slideshow_playback)
            elif "スライドショー停止" in text:
                self.master.after(0, self.stop_slideshow_playback)
            elif "次のスライド" in text:
                self.master.after(0, self.next_slide)

            query = post_audio_query(text)
            if query:
                wav = post_synthesis(query)
                if wav:
                    play_wavfile(wav)
                    # サイズ変更コマンドの場合、音声再生後に元のサイズに戻す
                    if "大きく" in text or "小さく" in text:
                        self.master.after(2000, lambda: self.master.geometry("950x1080")) # 初期サイズに戻す
                else:
                    self.master.after(0, lambda: print(">> 音声合成に失敗しました。", file=sys.stderr))
            else:
                self.master.after(0, lambda: print(">> 音声クエリの作成に失敗しました。", file=sys.stderr))
            
            # 発話が終了したら、動画アニメーションを停止
            self.master.after(0, self._end_speaking_animation)

        threading.Thread(target=actual_speak_process).start()

    def _start_speaking_animation(self):
        """VRoidキャラクターの動画アニメーションを開始する"""
        if not self.is_video_playing:
            try:
                self.cap = cv2.VideoCapture(self.speaking_video_path)
                if not self.cap.isOpened():
                    raise IOError(f"動画ファイル '{self.speaking_video_path}' を開けません。")
                
                # フレームレートを取得して、動画の遅延を調整
                fps = self.cap.get(cv2.CAP_PROP_FPS)
                if fps > 0:
                    self.video_frame_delay = int(1000 / fps)
                else:
                    self.video_frame_delay = 30 # デフォルト

                self.is_video_playing = True
                self._play_speaking_animation_video()
            except Exception as e:
                print(f"スピーキングアニメーションの開始中にエラー: {e}")
                self.update_chat_log(f"エラー: スピーキングアニメーションの開始に失敗しました: {e}", "red")
                self._end_speaking_animation() # エラー時はアニメーションをすぐに終了

    def _end_speaking_animation(self):
        """VRoidキャラクターの動画アニメーションを停止し、静止画に戻す"""
        if self.is_video_playing:
            self.is_video_playing = False
            if self.video_update_id:
                self.master.after_cancel(self.video_update_id)
                self.video_update_id = None
            if self.cap:
                self.cap.release()
                self.cap = None
            self.resize_vroid_image() # 元の静止画に戻す

if __name__ == "__main__":
    root = tk.Tk()
    app = VoiceChatApp(root)
    root.mainloop()
