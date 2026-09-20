# figures/ — fig-kit(図の型)と生成物

記事の図は手描きせず、**入力 JSON → 生成器 → SVG → PNG** で作る。生成器と入力を一緒に置くので、数値が変われば図も変わる。

| # | 生成器 | 入力 | 出力 | 道具 |
|---|---|---|---|---|
| F2 | `f2_matrix_grid.py` | `*.json`(2 軸の対応表) | `.svg` + `.png`(1600px) | Python + Inkscape CLI |
| F1 | pipeline_flow(段 + 矢印 + 失敗経路) | 予定 | | Inkscape |
| F3 | before_after(左右比較) | 予定 | | Inkscape / ffmpeg |
| F4 | bars_3d(x × y × 高さ) | 予定 | `.blend` + PNG + MP4 | Blender 5.x(bpy) |
| F5 | timeline_bitemporal(有効時間 × 知識時間) | 予定 | | Blender |

```bash
python -X utf8 f2_matrix_grid.py core_pack_quadrant.json
```

生成済みの PNG は commit する(記事側が raw URL で参照するため)。再生成はローカルで行う(CI では Blender / Inkscape を回さない)。
