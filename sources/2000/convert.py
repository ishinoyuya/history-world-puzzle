"""
2000年(西暦)の世界地図(aourednik/historical-basemaps由来のGeoJSON、
ファイル名は world_2000.geojson)を読み込み、経緯度(lon/lat)を
正距円筒図法でx,yに投影して、統合ページ用データ(../../data/2000.json)
に変換する。

このデータセットは193件と大規模で、ほぼ全てが2000年時点で国際的に
認知されていた主権国家・自治領・属領を指す実在の政体名であるため、
古代・中世のデータで行っていたような詳細な史実照合は不要で、
「Switzerland」(後述、ジオメトリ破損のため不採用)を除く192件を
そのまま採用する。

「Switzerland」は座標を確認したところ、実際のスイス領土とは無関係な
イタリア・フランス国境付近(モンブラン山塊周辺)のごく小さな3点だけ
から成る破損した図形(点4個で閉じただけの退化したポリゴン)であり、
国土を表すデータとして使用できないため不採用とする。

「Zaire」はデータ上の表記だが、実際には1997年にコンゴ民主共和国へ
改称されており2000年時点では旧称のため、実効支配の連続性に基づき
「コンゴ民主共和国(旧ザイール)」として読み替えて採用する。「Serbia」
「Montenegro」は2000年時点ではまだユーゴスラビア連邦共和国を構成する
共和国であり完全な独立国ではなかったが、データセット上は個別の地理的
領域として区別されているためそのままピース化し、その旨をラベルに
注記する。「Rapa Nui」(イースター島、チリ領)・「Greenland」(デンマーク
領)・「Hong Kong」(中国特別行政区)等、完全な主権国家ではない自治領・
属領についても、地理的に独立した明確な領域を持つため他の国と同様に
ピースとして採用する。

このデータセットは、これまでの年代とは異なり南北アメリカ・オセアニアの
両地域にも多数の実在する政体が含まれており、統合ページの全6地域モード
(ヨーロッパ・アフリカ・南北アメリカ・西アジア南アジア・東アジア東南
アジア・オセアニア)が初めて同時に有効になる年代である。

- 同名の複数featureは1つの国(MultiPolygon)にまとめる
- 日付変更線問題は「最大の一塊(陸地)」のbboxを当たり判定・ラベル位置の基準にする
- 採用しなかった領域(NAME未設定の無所属地域、Switzerlandの破損ジオメトリを含む)は
  操作不可の背景landとして残す
- 全ランド(採用+非採用)をshapelyでunionし、外周(海岸線)だけを抽出してoutlineとする
"""
import json
import math
import os
from collections import defaultdict

from shapely.geometry import shape
from shapely.ops import unary_union

BASE = os.path.dirname(__file__)

# 破損ジオメトリのため不採用とする名前
BROKEN_GEOMETRY = {"Switzerland"}

NAME_JA = {
    "Afghanistan": "アフガニスタン", "Albania": "アルバニア", "Algeria": "アルジェリア",
    "American Samoa": "アメリカ領サモア", "Andorra": "アンドラ", "Angola": "アンゴラ",
    "Anguilla": "アンギラ(英領)", "Antigua and Barbuda": "アンティグア・バーブーダ",
    "Argentina": "アルゼンチン", "Armenia": "アルメニア", "Australia": "オーストラリア",
    "Austria": "オーストリア", "Azerbaijan": "アゼルバイジャン", "Bahamas": "バハマ",
    "Bangladesh": "バングラデシュ", "Barbados": "バルバドス", "Belgium": "ベルギー",
    "Belize": "ベリーズ", "Benin": "ベナン", "Bhutan": "ブータン", "Bolivia": "ボリビア",
    "Bosnia and Herzegovina": "ボスニア・ヘルツェゴビナ", "Botswana": "ボツワナ",
    "Brazil": "ブラジル", "Brunei": "ブルネイ", "Bulgaria": "ブルガリア",
    "Burkina Faso": "ブルキナファソ", "Burma": "ミャンマー(ビルマ)", "Burundi": "ブルンジ",
    "Byelarus": "ベラルーシ", "Cambodia": "カンボジア", "Cameroon": "カメルーン",
    "Canada": "カナダ", "Central African Republic": "中央アフリカ共和国", "Chad": "チャド",
    "Chile": "チリ", "China": "中国", "Colombia": "コロンビア", "Congo": "コンゴ共和国",
    "Costa Rica": "コスタリカ", "Croatia": "クロアチア", "Cuba": "キューバ",
    "Cyprus": "キプロス", "Czech Republic": "チェコ", "Denmark": "デンマーク",
    "Djibouti": "ジブチ", "Dominica": "ドミニカ国", "Dominican Republic": "ドミニカ共和国",
    "Ecuador": "エクアドル", "Egypt": "エジプト", "El Salvador": "エルサルバドル",
    "Equatorial Guinea": "赤道ギニア", "Eritrea": "エリトリア", "Estonia": "エストニア",
    "Ethiopia": "エチオピア", "Fiji": "フィジー", "Finland": "フィンランド",
    "France": "フランス", "French Guiana": "フランス領ギアナ", "Gabon": "ガボン",
    "Gambia, The": "ガンビア", "Georgia": "ジョージア(グルジア)", "Germany": "ドイツ",
    "Ghana": "ガーナ", "Greece": "ギリシャ", "Greenland": "グリーンランド(デンマーク領)",
    "Grenada": "グレナダ", "Guadeloupe": "グアドループ(仏領)", "Guatemala": "グアテマラ",
    "Guinea": "ギニア", "Guinea-Bissau": "ギニアビサウ", "Guyana": "ガイアナ",
    "Haiti": "ハイチ", "Honduras": "ホンジュラス", "Hong Kong": "香港(中国特別行政区)",
    "Hungary": "ハンガリー", "Iceland": "アイスランド", "India": "インド",
    "Indonesia": "インドネシア", "Iran": "イラン", "Iraq": "イラク", "Ireland": "アイルランド",
    "Israel": "イスラエル", "Italy": "イタリア", "Ivory Coast": "コートジボワール",
    "Jamaica": "ジャマイカ", "Japan": "日本", "Jordan": "ヨルダン",
    "Kazakhstan": "カザフスタン", "Kenya": "ケニア",
    "Korea, Democratic People's Republic of": "北朝鮮",
    "Korea, Republic of": "韓国", "Kuwait": "クウェート", "Kyrgyzstan": "キルギス",
    "Laos": "ラオス", "Latvia": "ラトビア", "Lebanon": "レバノン", "Lesotho": "レソト",
    "Liberia": "リベリア", "Libya": "リビア", "Liechtenstein": "リヒテンシュタイン",
    "Lithuania": "リトアニア", "Luxembourg": "ルクセンブルク", "Macedonia": "マケドニア",
    "Madagascar": "マダガスカル", "Malawi": "マラウイ", "Malaysia": "マレーシア",
    "Mali": "マリ", "Malta": "マルタ", "Martinique": "マルティニーク(仏領)",
    "Mauritania": "モーリタニア", "Mexico": "メキシコ", "Moldova": "モルドバ",
    "Mongolia": "モンゴル", "Montenegro": "モンテネグロ(当時はユーゴスラビア連邦構成体)",
    "Montserrat": "モントセラト(英領)", "Morocco": "モロッコ", "Mozambique": "モザンビーク",
    "Namibia": "ナミビア", "Nepal": "ネパール", "Netherlands": "オランダ",
    "Netherlands Antilles": "オランダ領アンティル",
    "New Zealand": "ニュージーランド", "Nicaragua": "ニカラグア", "Niger": "ニジェール",
    "Nigeria": "ナイジェリア", "Niue": "ニウエ", "Norway": "ノルウェー", "Oman": "オマーン",
    "Pakistan": "パキスタン", "Panama": "パナマ", "Papua New Guinea": "パプアニューギニア",
    "Paraguay": "パラグアイ", "Peru": "ペルー", "Philippines": "フィリピン",
    "Poland": "ポーランド", "Portugal": "ポルトガル", "Puerto Rico": "プエルトリコ(米自治領)",
    "Qatar": "カタール", "Rapa Nui": "イースター島(チリ領)", "Romania": "ルーマニア",
    "Russia": "ロシア", "Rwanda": "ルワンダ", "Saint Barthelemy": "サン・バルテルミー(仏領)",
    "Saint Kitts and Nevis": "セントクリストファー・ネイビス",
    "Saint Lucia": "セントルシア", "Saint Martin": "サン・マルタン(仏領)",
    "Saint Vincent and the Grenadines": "セントビンセント・グレナディーン",
    "Samoa": "サモア", "Saudi Arabia": "サウジアラビア", "Senegal": "セネガル",
    "Serbia": "セルビア(当時はユーゴスラビア連邦構成体)",
    "Sierra Leone": "シエラレオネ", "Slovakia": "スロバキア", "Slovenia": "スロベニア",
    "Somalia": "ソマリア", "South Africa": "南アフリカ", "Spain": "スペイン",
    "Sri Lanka": "スリランカ", "Sudan": "スーダン", "Suriname": "スリナム",
    "Swaziland": "スワジランド", "Sweden": "スウェーデン", "Syria": "シリア",
    "Taiwan": "台湾", "Tajikistan": "タジキスタン",
    "Tanzania, United Republic of": "タンザニア", "Thailand": "タイ", "Togo": "トーゴ",
    "Tonga": "トンガ", "Trinidad": "トリニダード・トバゴ", "Tunisia": "チュニジア",
    "Turkey": "トルコ",
    "Turkish Cypriot-administered area": "北キプロス・トルコ共和国(未承認国家)",
    "Turkmenistan": "トルクメニスタン",
    "Turks and Caicos Islands": "タークス・カイコス諸島(英領)", "Uganda": "ウガンダ",
    "Ukraine": "ウクライナ", "United Arab Emirates": "アラブ首長国連邦",
    "United Kingdom": "イギリス", "United States": "アメリカ合衆国",
    "United States Virgin Islands": "米領ヴァージン諸島", "Uruguay": "ウルグアイ",
    "Uzbekistan": "ウズベキスタン", "Venezuela": "ベネズエラ", "Vietnam": "ベトナム",
    "Wallis and Futuna Islands": "ウォリス・フツナ(仏領)",
    "Western Sahara": "西サハラ(係争地)", "Yemen": "イエメン",
    "Zaire": "コンゴ民主共和国(旧ザイール)", "Zambia": "ザンビア",
    "Zimbabwe": "ジンバブエ",
}

INCLUDE_NAMES = set(NAME_JA.keys())

# 地域モード用の区分。この年代は南北アメリカ・オセアニアにも多数の
# 実在国家が存在するため、初めて全6地域モードが有効になる。
REGIONS = {
    "europe": [
        "Albania", "Andorra", "Austria", "Belgium", "Bosnia and Herzegovina",
        "Bulgaria", "Byelarus", "Croatia", "Cyprus", "Czech Republic",
        "Denmark", "Estonia", "Finland", "France", "Georgia", "Germany",
        "Greece", "Hungary", "Iceland", "Ireland", "Italy", "Latvia",
        "Liechtenstein", "Lithuania", "Luxembourg", "Macedonia", "Malta",
        "Moldova", "Montenegro", "Netherlands", "Norway", "Poland",
        "Portugal", "Romania", "Russia", "Serbia", "Slovakia", "Slovenia",
        "Spain", "Sweden", "Turkish Cypriot-administered area", "Ukraine",
        "United Kingdom", "Armenia", "Azerbaijan",
    ],
    "africa": [
        "Algeria", "Angola", "Benin", "Botswana", "Burkina Faso", "Burundi",
        "Cameroon", "Central African Republic", "Chad", "Congo",
        "Djibouti", "Egypt", "Equatorial Guinea", "Eritrea", "Ethiopia",
        "Gabon", "Gambia, The", "Ghana", "Guinea", "Guinea-Bissau",
        "Ivory Coast", "Kenya", "Lesotho", "Liberia", "Libya", "Madagascar",
        "Malawi", "Mali", "Mauritania", "Morocco", "Mozambique", "Namibia",
        "Niger", "Nigeria", "Rwanda", "Senegal", "Sierra Leone", "Somalia",
        "South Africa", "Sudan", "Swaziland", "Tanzania, United Republic of",
        "Togo", "Tunisia", "Uganda", "Western Sahara", "Zaire", "Zambia",
        "Zimbabwe",
    ],
    "americas": [
        "Anguilla", "Antigua and Barbuda", "Argentina", "Bahamas",
        "Barbados", "Belize", "Bolivia", "Brazil", "Canada", "Chile",
        "Colombia", "Costa Rica", "Cuba", "Dominica", "Dominican Republic",
        "Ecuador", "El Salvador", "French Guiana", "Greenland", "Grenada",
        "Guadeloupe", "Guatemala", "Guyana", "Haiti", "Honduras",
        "Jamaica", "Martinique", "Mexico", "Montserrat",
        "Netherlands Antilles", "Nicaragua", "Panama", "Paraguay", "Peru",
        "Puerto Rico", "Saint Barthelemy", "Saint Kitts and Nevis",
        "Saint Lucia", "Saint Martin", "Saint Vincent and the Grenadines",
        "Suriname", "Trinidad", "Turks and Caicos Islands",
        "United States", "United States Virgin Islands", "Uruguay",
        "Venezuela",
    ],
    "wsasia": [
        "Afghanistan", "Bangladesh", "Bhutan", "India", "Iran", "Iraq",
        "Israel", "Jordan", "Kazakhstan", "Kuwait", "Kyrgyzstan", "Lebanon",
        "Nepal", "Oman", "Pakistan", "Qatar", "Saudi Arabia", "Sri Lanka",
        "Syria", "Tajikistan", "Turkey", "Turkmenistan",
        "United Arab Emirates", "Uzbekistan", "Yemen",
    ],
    "easia": [
        "Brunei", "Burma", "Cambodia", "China", "Hong Kong", "Indonesia",
        "Japan", "Korea, Democratic People's Republic of",
        "Korea, Republic of", "Laos", "Malaysia", "Mongolia",
        "Philippines", "Taiwan", "Thailand", "Vietnam",
    ],
    "oceania": [
        "American Samoa", "Australia", "Fiji", "New Zealand", "Niue",
        "Papua New Guinea", "Rapa Nui", "Samoa", "Tonga",
        "Wallis and Futuna Islands",
    ],
}
COUNTRY_REGIONS = {}
for region, names in REGIONS.items():
    for n in names:
        COUNTRY_REGIONS.setdefault(n, []).append(region)

# 地図上のラベル用の短縮表記(長すぎてピース内に収まらない名前だけ上書き)
LABEL_JA_SHORT = {
    "Anguilla": "アンギラ", "Burma": "ミャンマー", "Georgia": "ジョージア",
    "Gambia, The": "ガンビア", "Greenland": "グリーンランド",
    "Guadeloupe": "グアドループ", "Hong Kong": "香港",
    "Korea, Democratic People's Republic of": "北朝鮮",
    "Korea, Republic of": "韓国", "Martinique": "マルティニーク",
    "Montenegro": "モンテネグロ", "Montserrat": "モントセラト",
    "Puerto Rico": "プエルトリコ", "Rapa Nui": "イースター島",
    "Saint Barthelemy": "サン・バルテルミー", "Saint Martin": "サン・マルタン",
    "Serbia": "セルビア", "Tanzania, United Republic of": "タンザニア",
    "Turkish Cypriot-administered area": "北キプロス",
    "Turks and Caicos Islands": "タークス・カイコス諸島",
    "Wallis and Futuna Islands": "ウォリス・フツナ", "Western Sahara": "西サハラ",
    "Zaire": "コンゴ民主共和国",
}


def project(lon, lat):
    return (lon, -lat)


def ring_area_and_bbox(ring):
    area = 0.0
    minx = miny = float("inf")
    maxx = maxy = float("-inf")
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        area += x1 * y2 - x2 * y1
        minx = min(minx, x1); maxx = max(maxx, x1)
        miny = min(miny, y1); maxy = max(maxy, y1)
    return abs(area) / 2.0, (minx, miny, maxx, maxy)


def largest_part(proj_polygons):
    """複数島/飛び地からなる国の中で最大の陸塊(外周ring)の面積とbboxを返す"""
    best_area, best_bbox = -1.0, None
    for poly in proj_polygons:
        outer = poly[0]
        area, bbox = ring_area_and_bbox(outer)
        if area > best_area:
            best_area, best_bbox = area, bbox
    return best_area, best_bbox


def total_area(proj_polygons):
    total = 0.0
    for poly in proj_polygons:
        outer_area, _ = ring_area_and_bbox(poly[0])
        hole_area = sum(ring_area_and_bbox(r)[0] for r in poly[1:])
        total += outer_area - hole_area
    return total


def point_in_polygons(pt, proj_polygons):
    x, y = pt
    for poly in proj_polygons:
        crossings = 0
        for ring in poly:
            n = len(ring)
            for i in range(n):
                x1, y1 = ring[i]
                x2, y2 = ring[(i + 1) % n]
                if (y1 > y) != (y2 > y):
                    xin = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
                    if x < xin:
                        crossings += 1
        if crossings % 2 == 1:
            return True
    return False


def dist_point_segment(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(px - x1, py - y1)
    t = ((px - x1) * dx + (py - y1) * dy) / (dx * dx + dy * dy)
    t = max(0.0, min(1.0, t))
    cx, cy = x1 + t * dx, y1 + t * dy
    return math.hypot(px - cx, py - cy)


def min_dist_to_boundary(pt, proj_polygons):
    x, y = pt
    best = float("inf")
    for poly in proj_polygons:
        for ring in poly:
            n = len(ring)
            for i in range(n):
                x1, y1 = ring[i]
                x2, y2 = ring[(i + 1) % n]
                d = dist_point_segment(x, y, x1, y1, x2, y2)
                if d < best:
                    best = d
    return best


def visual_center(proj_polygons, search_bbox):
    """search_bbox(=最大陸塊のbbox)の範囲内だけをグリッド探索して、
    ポリゴン内部で最も縁から遠い点を求める(飛び地・日付変更線越えでも暴走しない)"""
    minx, miny, maxx, maxy = search_bbox
    best_pt = [(minx + maxx) / 2, (miny + maxy) / 2]
    best_score = -1.0

    def search(cx0, cy0, cx1, cy1, steps):
        nonlocal best_pt, best_score
        for i in range(steps + 1):
            for j in range(steps + 1):
                x = cx0 + (cx1 - cx0) * i / steps
                y = cy0 + (cy1 - cy0) * j / steps
                if point_in_polygons((x, y), proj_polygons):
                    d = min_dist_to_boundary((x, y), proj_polygons)
                    if d > best_score:
                        best_score = d
                        best_pt = [x, y]

    search(minx, miny, maxx, maxy, 20)
    span_x, span_y = (maxx - minx), (maxy - miny)
    for factor in (0.22, 0.07):
        wx, wy = max(span_x * factor, 1e-6), max(span_y * factor, 1e-6)
        bx, by = best_pt
        search(bx - wx, by - wy, bx + wx, by + wy, 12)

    return best_pt


def multipolygon_to_proj_polygons(coords):
    """GeoJSON MultiPolygonのcoordinatesを投影済み[[ring,...],...]に変換"""
    polygons = []
    for poly in coords:
        rings = [[project(lon, lat) for lon, lat in ring] for ring in poly]
        polygons.append(rings)
    return polygons


def boundary_to_polylines(geom, min_area=0.0):
    """shapelyのunion結果(Polygon/MultiPolygon)のboundaryを、
    キャンバス描画用の点列リストに変換する(内部境界=国境は含まれない)。
    min_area未満の小片(bufferで埋めきれなかった隙間の残骸など)は除外する。"""
    lines = []

    def add_ring(coords):
        lines.append([list(project(lon, lat)) for lon, lat in coords])

    polys = geom.geoms if geom.geom_type == "MultiPolygon" else [geom]
    for poly in polys:
        if poly.area < min_area:
            continue
        add_ring(list(poly.exterior.coords))
        for interior in poly.interiors:
            add_ring(list(interior.coords))
    return lines


def main():
    src = json.load(open(os.path.join(BASE, "world_2000.geojson"), encoding="utf-8"))
    feats = src["features"]

    named = defaultdict(list)  # name -> list of raw MultiPolygon coordinate lists
    named_props = {}
    all_shapes = []
    unnamed_polygons = []  # NAME未設定(無所属地域)の投影済みポリゴン

    for f in feats:
        name = f["properties"].get("NAME")
        if name is not None:
            name = name.strip() or None
        coords = f["geometry"]["coordinates"]  # 全featureがMultiPolygon
        all_shapes.append(shape(f["geometry"]))
        if name and name not in BROKEN_GEOMETRY:
            named[name].append(coords)
            named_props[name] = f["properties"]
        else:
            unnamed_polygons.append(multipolygon_to_proj_polygons(coords))

    missing_ja = []
    countries_out = []
    excluded_polygons = list(unnamed_polygons)  # 採用しなかった領域も陸地としては背景に残す
    for name, coord_groups in named.items():
        merged_coords = [poly for group in coord_groups for poly in group]
        proj_polygons = multipolygon_to_proj_polygons(merged_coords)

        if name not in INCLUDE_NAMES:
            excluded_polygons.append(proj_polygons)
            continue

        if name not in NAME_JA:
            missing_ja.append(name)

        area = total_area(proj_polygons)
        _, main_bbox = largest_part(proj_polygons)
        minx, miny, maxx, maxy = main_bbox
        centroid = [(minx + maxx) / 2, (miny + maxy) / 2]
        label_pt = visual_center(proj_polygons, main_bbox)

        props = named_props[name]
        countries_out.append({
            "id": name,
            "name": name,
            "nameJa": NAME_JA.get(name, name),
            "labelJa": LABEL_JA_SHORT.get(name, NAME_JA.get(name, name)),
            "regions": COUNTRY_REGIONS.get(name, []),
            "abbrev": props.get("ABBREVN") or name,
            "polygons": proj_polygons,
            "bbox": [minx, miny, maxx, maxy],
            "centroid": centroid,
            "labelPoint": label_pt,
            "area": area,
        })

    countries_out.sort(key=lambda c: -c["area"])

    neutral_out = excluded_polygons

    # 全ランドをunionして海岸線(=国境を含まない外周)を抽出。
    # このデータセットは隣接国同士の境界が厳密に一致していない(小さな隙間がある)ため、
    # 素直にunionすると隙間の分だけ大量の細切れポリゴン(ノイズ線)が残ってしまう。
    # 一度太らせてからunionし、同じ分だけ痩せさせる("buffer-unbuffer")ことで
    # 小さな隙間を埋めてから外周を抽出する。
    buf = 0.2
    grown = [s.buffer(buf, join_style=2) for s in all_shapes]
    world_union = unary_union(grown).buffer(-buf, join_style=2)
    outline = boundary_to_polylines(world_union, min_area=0.3)

    data = {
        "countries": countries_out,
        "neutralLand": neutral_out,
        "outline": outline,
    }

    # 統合ページ(world-history-puzzle)の data/2000.json に直接出力する
    out_dir = os.path.join(BASE, "..", "..", "data")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "2000.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

    print(f"countries: {len(countries_out)}")
    print(f"excluded (kept as background): {len(excluded_polygons)}")
    print(f"neutral land pieces: {len(neutral_out)}")
    print(f"outline polylines: {len(outline)}")
    print(f"wrote {out_path}")
    if missing_ja:
        print(f"WARNING: missing NAME_JA for {len(missing_ja)}: {missing_ja}")
    missing_region = [c["name"] for c in countries_out if not c["regions"]]
    if missing_region:
        print(f"WARNING: missing region assignment for {len(missing_region)}: {missing_region}")
    unknown_include = INCLUDE_NAMES - set(named.keys())
    if unknown_include:
        print(f"WARNING: INCLUDE_NAMES not found in source data: {sorted(unknown_include)}")


if __name__ == "__main__":
    main()
