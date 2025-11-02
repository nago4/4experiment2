import pydicom
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider, Button
import os
import tkinter as tk
from tkinter import filedialog
from functools import partial

# --- 日本語フォント設定 ---
try:
    plt.rcParams['font.family'] = 'Meiryo' 
except:
    plt.rcParams['font.family'] = 'sans-serif' 
plt.rcParams['axes.unicode_minus'] = False 
# -------------------------

# --- 1. グローバル変数の設定 ---
GRAYSCALE_MAX = 255
DICOM_VOLUME = None 
DICOM_SERIES_DS = []
# Z, Y, X軸の現在のインデックス
current_index = {'Z': 0, 'Y': 0, 'X': 0}
current_plane = 'Coronal' # 現在表示している切替面 ('Coronal' または 'Sagittal')

# Matplotlibオブジェクト
fig = None
axs = {}
image_displays = {}
sliders = {}
reformation_lines = {}
info_text = {}
header_text = {}
initial_root = None

# --- 2. 画像処理関数 (Windowing) ---
def apply_windowing(image_data, window_level, window_width):
    """ WL/WWを適用して画像を8bit表示用に変換 """
    min_value = window_level - (window_width / 2.0)
    max_value = window_level + (window_width / 2.0)

    image_float = image_data.astype(np.float64)
    image_float = np.clip(image_float, min_value, max_value)
    
    image_float = (image_float - min_value) / window_width * GRAYSCALE_MAX
    image_float = np.clip(image_float, 0, GRAYSCALE_MAX)
    
    return image_float.astype(np.uint8)

# --- 3. DICOMフォルダ読み込みと3Dボリューム構築 ---
def load_dicom_data(folder_path):
    # ... (前回のコードと同じため省略、機能は保持) ...
    global DICOM_VOLUME, DICOM_SERIES_DS
    DICOM_SERIES_DS.clear()
    
    dicom_files = []
    for filename in os.listdir(folder_path):
        if filename.endswith(('.dcm', '.')):
            file_path = os.path.join(folder_path, filename)
            try:
                ds = pydicom.dcmread(file_path)
                if hasattr(ds, 'pixel_array'):
                    dicom_files.append(ds)
            except:
                continue

    if not dicom_files:
        print("エラー: フォルダ内に有効なDICOMファイルが見つかりませんでした。")
        return False, None

    try:
        dicom_files.sort(key=lambda x: int(getattr(x, 'InstanceNumber', 0)))
    except:
        pass
        
    DICOM_SERIES_DS = dicom_files
    
    slices = [s.pixel_array for s in DICOM_SERIES_DS]
    volume = np.stack(slices, axis=0).astype(np.int16) 

    slope = getattr(DICOM_SERIES_DS[0], 'RescaleSlope', 1)
    intercept = getattr(DICOM_SERIES_DS[0], 'RescaleIntercept', 0)
    if slope != 1 or intercept != 0:
        volume = volume * slope + intercept
    
    DICOM_VOLUME = volume
    return True, DICOM_SERIES_DS[0]

# --- 4. 画像の更新と参照線の描画 ---
def update_viewer(val=None, plane=None):
    """
    スライダー/ボタン操作時に画像を更新し、参照線を描画する。
    """
    global image_displays, reformation_lines, current_index, sliders, info_text, current_plane

    if DICOM_VOLUME is None: return

    Z, Y, X = DICOM_VOLUME.shape
    wl = sliders['wl'].val
    ww = sliders['ww'].val
    
    # スライダーから現在のインデックスを取得
    current_index['Z'] = int(sliders['Z'].val)
    current_index['Y'] = int(sliders['Y'].val)
    current_index['X'] = int(sliders['X'].val)

    # ------------------ 1. 画像の更新 ------------------
    
    # Axial画像 (原画像系列)
    axial_slice = DICOM_VOLUME[current_index['Z'], :, :] 
    image_displays['axial'].set_data(apply_windowing(axial_slice, wl, ww))
    
    # 切替画面の画像更新
    if current_plane == 'Coronal':
        # Coronal画像 (ZxX平面, Y軸インデックスでスライス)
        coronal_slice = DICOM_VOLUME[:, current_index['Y'], :] 
        image_displays['secondary'].set_data(apply_windowing(coronal_slice, wl, ww))
        axs['secondary'].set_title(f"Coronal (Y: {current_index['Y']+1}/{Y})", fontsize=10)
    else: # Sagittal
        # Sagittal画像 (ZxY平面, X軸インデックスでスライス)
        sagittal_slice = DICOM_VOLUME[:, :, current_index['X']]
        image_displays['secondary'].set_data(apply_windowing(sagittal_slice, wl, ww))
        axs['secondary'].set_title(f"Sagittal (X: {current_index['X']+1}/{X})", fontsize=10)


    # ------------------ 2. 参照線の更新 ------------------
    
    # Axial (YxX) 画像の参照線
    # 既存の参照線を非表示にする
    reformation_lines['coronal'].set_visible(False)
    reformation_lines['sagittal'].set_visible(False)

    if current_plane == 'Coronal':
        # Coronal (Y軸切断) の線 -> Y軸位置に水平線 (横線)
        reformation_lines['coronal'].set_ydata([current_index['Y'], current_index['Y']])
        reformation_lines['coronal'].set_visible(True)
    else: # Sagittal
        # Sagittal (X軸切断) の線 -> X軸位置に垂直線 (縦線)
        reformation_lines['sagittal'].set_xdata([current_index['X'], current_index['X']])
        reformation_lines['sagittal'].set_visible(True)
        
    # 切替画面側の参照線 (常にAxialのZ軸位置を示す横線)
    reformation_lines['secondary_axial'].set_ydata([current_index['Z'], current_index['Z']])

    # ------------------ 3. タイトル/情報テキストの更新 ------------------
    axs['axial'].set_title(f"Axial (Z: {current_index['Z']+1}/{Z})", fontsize=10)
    info_text['wl_ww'].set_text(f"WL: {int(wl)}, WW: {int(ww)}")

    # スライダーの有効/無効を切り替える
    for slider_key in ['Y', 'X']:
        sliders[slider_key].set_active(False) # 一旦全て無効化
        
    if current_plane == 'Coronal':
        sliders['Y'].set_active(True)
    else: # Sagittal
        sliders['X'].set_active(True)
        
    fig.canvas.draw_idle()


# --- 5. 切替ボタンのコールバック関数 ---
def toggle_plane(event):
    """ CoronalとSagittalの表示を切り替える """
    global current_plane
    if current_plane == 'Coronal':
        current_plane = 'Sagittal'
        sliders['Y'].set_active(False)
        sliders['X'].set_active(True)
    else:
        current_plane = 'Coronal'
        sliders['X'].set_active(False)
        sliders['Y'].set_active(True)
        
    # ボタンのラベルを更新 (今回は省略。Matplotlibでは複雑なため)
    
    # 参照線と画像を更新
    update_viewer()


# --- 6. GUI初期化とメインロジック ---
def select_folder_and_run(tk_root):
    # ... (前回のコードと同じため省略) ...
    folder_path = filedialog.askdirectory(title="DICOM画像系列が入ったフォルダを選択")
    
    if not folder_path:
        return

    success, ds_info = load_dicom_data(folder_path)
    if success:
        tk_root.destroy()
        initialize_viewer(ds_info)
    else:
        print("データ読み込みに失敗しました。")


def initialize_viewer(ds_info):
    """ Viewerウィンドウとウィジェットを初期化する """
    global fig, axs, image_displays, sliders, reformation_lines, info_text, header_text, current_plane
    
    current_plane = 'Coronal'

    Z, Y, X = DICOM_VOLUME.shape
    
    # --- WL/WWの初期値設定 ---
    # DICOM ヘッダの WindowCenter / WindowWidth は配列の場合があるため安全に取り出す
    def _safe_window(ds, attr_name, default):
        val = getattr(ds, attr_name, default)
        try:
            # シーケンス（リスト等）の場合は先頭要素を使う
            if isinstance(val, (list, tuple, np.ndarray)):
                return float(val[0])
            return float(val)
        except Exception:
            return float(default)

    initial_wl = _safe_window(ds_info, 'WindowCenter', 1000.0)
    initial_ww = _safe_window(ds_info, 'WindowWidth', 2000.0)

    # --- グラフ領域のレイアウト設定 (2画像 + 1情報/スライダーパネル) ---
    # constrained_layout=True にしてリサイズ時にレイアウトが自動調整されるようにする
    fig = plt.figure(figsize=(12, 6.5), constrained_layout=True)
    # 1段目: 画像 2枚、 2段目: Info/Sliders (subgridspec で左右を分割)
    gs = fig.add_gridspec(2, 2, height_ratios=[5, 2], hspace=0.1, wspace=0.05)

    axs['axial'] = fig.add_subplot(gs[0, 0])      # 左: Axial
    axs['secondary'] = fig.add_subplot(gs[0, 1])  # 右: Coronal/Sagittal切替

    # Info領域を左:ヘッダー、右:スライダー群 で分割する
    # 右側の行数を1つ増やし、WL/WW テキスト領域と面切替ボタンを別に配置して重なりを防止
    info_sub = gs[1, :].subgridspec(7, 2, width_ratios=[1.5, 1], hspace=0.12)
    axs['info_left'] = fig.add_subplot(info_sub[:, 0])    # 左側ヘッダー領域 (複数行を占有)
    axs['info_left'].axis('off')

    # 右側は個別の小さなサブプロットを作り、そこに WL/WW テキスト、Button、Slider を置く
    ax_info_text = fig.add_subplot(info_sub[0, 1])
    ax_button = fig.add_subplot(info_sub[1, 0:2])  # ボタン用サブプロット (横幅2列分)
    ax_wl = fig.add_subplot(info_sub[2, 1])
    ax_ww = fig.add_subplot(info_sub[3, 1])
    ax_z = fig.add_subplot(info_sub[4, 1])
    ax_y = fig.add_subplot(info_sub[5, 1])
    ax_x = fig.add_subplot(info_sub[6, 1])

    # 画像パネルの調整: アスペクトを 'auto' にして軸サイズに合わせて画像が伸縮するようにする
    for key in ['axial', 'secondary']:
        axs[key].axis('off')
        axs[key].set_aspect('auto')
    
    # --- DICOMヘッダー情報表示 (整形表示) ---
    rows = ds_info.Rows 
    cols = ds_info.Columns
    slice_thickness = getattr(ds_info, 'SliceThickness', 'N/A')
    
    # Infoパネル内の配置座標
    # WL/WW情報とヘッダー情報を横に並べる
    
    # ----------------------------------------------------------------------
    # 左側 (ヘッダー情報)
    # ----------------------------------------------------------------------
    # 左側 Info 表示
    axs['info_left'].text(0.02, 0.96, "--- DICOMヘッダー情報 ---", fontsize=10, weight='bold', va='top')
    axs['info_left'].text(0.02, 0.72, f"画像の縦横サイズ: {rows}x{cols}", fontsize=9, va='top')
    axs['info_left'].text(0.02, 0.50, f"スライス厚: {slice_thickness} mm", fontsize=9, va='top')
    axs['info_left'].text(0.02, 0.28, f"スライスの数: {Z}", fontsize=9, va='top')
    
    # ----------------------------------------------------------------------
    # 右側 (スライダー)
    # ----------------------------------------------------------------------
    
    # WL/WW 情報テキスト
    # WL/WW 表示（右上の小領域に表示）
    info_text['wl_ww'] = ax_info_text.text(0.5, 0.5, f"WL: {int(initial_wl)},\nWW: {int(initial_ww)}", ha='center', va='center', fontsize=9, color='darkblue')
    ax_info_text.axis('off')

    # Slider を右側のサブプロットに作成 (各サブプロットはリサイズに合わせて伸縮する)
    ax_wl.set_facecolor('lightgoldenrodyellow'); ax_wl.set_xticks([]); ax_wl.set_yticks([])
    ax_ww.set_facecolor('lightgoldenrodyellow'); ax_ww.set_xticks([]); ax_ww.set_yticks([])
    ax_z.set_facecolor('lightcoral'); ax_z.set_xticks([]); ax_z.set_yticks([])
    ax_y.set_facecolor('lime'); ax_y.set_xticks([]); ax_y.set_yticks([])
    ax_x.set_facecolor('yellow'); ax_x.set_xticks([]); ax_x.set_yticks([])

    sliders['wl'] = Slider(ax_wl, 'WL', -2000, 4096, valinit=initial_wl, valstep=10)
    sliders['ww'] = Slider(ax_ww, 'WW', 1, 8192, valinit=initial_ww, valstep=10)
    sliders['Z'] = Slider(ax_z, 'Axial Slice (Z)', 0, Z - 1, valinit=Z//2, valstep=1)
    sliders['Y'] = Slider(ax_y, 'Coronal (Y)', 0, Y - 1, valinit=Y//2, valstep=1)
    sliders['Y'].set_active(True)
    sliders['X'] = Slider(ax_x, 'Sagittal (X)', 0, X - 1, valinit=X//2, valstep=1)
    sliders['X'].set_active(False)

    # --- 画像の初期表示 ---
    current_index['Z'] = Z//2
    current_index['Y'] = Y//2
    current_index['X'] = X//2
    
    # Axial (YxX)
    # 画像の初期表示: imshow は aspect='auto' を使い、interpolation を nearest に
    image_displays['axial'] = axs['axial'].imshow(
        apply_windowing(DICOM_VOLUME[Z//2, :, :], initial_wl, initial_ww), cmap=plt.cm.gray, aspect='auto', interpolation='nearest')

    # Secondary (Coronalを初期表示). DICOM_VOLUME[:, Y//2, :] の縦方向 (Z) が画像の縦幅となるため
    # aspect='auto' により軸サイズに合わせて縦幅も確保され、切れて表示される問題を軽減する
    image_displays['secondary'] = axs['secondary'].imshow(
        apply_windowing(DICOM_VOLUME[:, Y//2, :], initial_wl, initial_ww), cmap=plt.cm.gray, aspect='auto', interpolation='nearest')


    # --- 参照線（Reformation Line）の初期描画 ---
    # Axial (原画像系列) 上の線: Coronal (横線) と Sagittal (縦線) の両方を準備し、切替で表示
    reformation_lines['coronal'] = axs['axial'].axhline(y=current_index['Y'], color='lime', linewidth=1)
    reformation_lines['sagittal'] = axs['axial'].axvline(x=current_index['X'], color='yellow', linewidth=1, visible=False) # 初期はSagittalは非表示
    
    # Secondary (切替画面) 上の線: Axialの切断線 (常に横線)
    reformation_lines['secondary_axial'] = axs['secondary'].axhline(y=current_index['Z'], color='red', linewidth=1)

    # --- 切替ボタンの作成 ---
    # ボタンは専用の ax_button 上に配置
    ax_button.axis('off')
    button = Button(ax_button, '面切替\n(Coronal/Sagittal)', color='lightgray', hovercolor='0.975')
    button.on_clicked(toggle_plane)
    
    # --- スライダーに更新関数を紐づけ ---
    sliders['wl'].on_changed(update_viewer)
    sliders['ww'].on_changed(update_viewer)
    sliders['Z'].on_changed(update_viewer)
    sliders['Y'].on_changed(update_viewer)
    sliders['X'].on_changed(update_viewer)

    update_viewer() 
    
    plt.show()

# --- 7. メイン実行ロジック (Tkinterで初期ボタンを表示) ---
# ... (前回のコードと同じため省略) ...
def run_initial_window():
    global initial_root
    
    initial_root = tk.Tk()
    initial_root.title("DICOM Viewer Launcher")
    initial_root.geometry("300x150+500+300")
    
    tk.Label(initial_root, text="知能情報実験実習2 - DICOM Viewer", font=("Meiryo", 10)).pack(pady=10)
    
    tk.Button(initial_root, text="DICOMフォルダを開く", 
              command=lambda: select_folder_and_run(initial_root),
              bg="skyblue", fg="black", font=("Meiryo", 10, "bold")).pack(pady=15)

    initial_root.mainloop()

if __name__ == '__main__':
    run_initial_window()