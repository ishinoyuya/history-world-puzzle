"""
1000年の世界地図(aourednik/historical-basemaps由来のGeoJSON)を読み込み、
経緯度(lon/lat)を正距円筒図法でx,yに投影して、統合ページ用データ
(../../data/1000.json)に変換する。

このデータセットは129件と小規模。実在した国家・帝国・王国だけを選ぶ
「採用リスト方式」にする。

1000年は後ウマイヤ朝(コルドバ・カリフ国)最盛期、ファーティマ朝
(エジプト)、ブワイフ朝(バグダード、複数の分家)、ビザンツ帝国も
健在。中国は宋・遼・西夏。ルーシはキエフ大公国が最盛期。ハンガリーは
建国(1000年)直前のためマジャル人の部族連合として、シチリアは
ノルマン征服前のためイスラム首長国として、ブルガリアは第一帝国が
まだ健在(1018年まで)、ベネヴェント公国も健在(1050年代まで)として
収録した。トゥールーズ伯領などブルガリア第二帝国・マリ帝国・
スコータイ王朝といった明確に時代が早すぎる候補は除外している。

- 同名の複数featureは1つの国(MultiPolygon)にまとめる
- 日付変更線問題は「最大の一塊(陸地)」のbboxを当たり判定・ラベル位置の基準にする
- 採用しなかった領域は操作不可の背景land(neutral)として残す
- 全ランド(採用+非採用)をshapelyでunionし、外周(海岸線)だけを抽出してoutlineとする
"""
import json
import math
import os
from collections import defaultdict

from shapely.geometry import shape
from shapely.ops import unary_union

BASE = os.path.dirname(__file__)

# 実在した国家・帝国・王国のみを採用(129件中76件)。
INCLUDE_NAMES = {
    "Denmark-Norway", "Kyivan Rus", "Volga Bulgars", "Byzantine Empire",
    "Holy Roman Empire", "Caliphate of Córdoba", "Kingdom of France", "Poland",
    "Bulgar Khanate", "Sweden", "Icelandic Commonwealth", "León", "Burgandy",
    "Scotland", "Pomerania", "Duchy of Swabia", "Castilla", "Serbia",
    "Navarre", "Croatia", "Dutchy of Benevento", "Britany", "Emirate of Sicily",
    "Sardinia", "Aragón", "Corsica", "Cyprus", "Venice", "Magyars", "Khazars",
    "Peshemegs", "Kimek-Kipchak khaganate", "England",
    "Fatimid Caliphate", "Makkura", "Madagascar", "Alwa", "Great Zimbabwe",
    "Kanem", "Ghana", "Takrur",
    "Tiahuanaco Empire", "Huari Empire", "Chimú Empire", "Toltec Empire",
    "Tibet", "Buwayhid Emirates", "Buyid Emirate", "Rajput kingdoms",
    "Ghaznavid Emirate", "Chalukya Empire", "Palas", "Chola state",
    "Pratiharas", "Kingdom of Georgia", "Armenia", "Chauhans", "Yemen",
    "Muscat", "Orissa", "Shirvan", "Kalinga",
    "Song Empire", "Liao", "Xixia", "Srivijaya Empire", "Khmer Empire",
    "Imperial Japan (Fujiwara)", "Kingdom of Pagan", "Korea", "East Java",
    "Annam", "Champa", "Haripunjaya", "Dvaravati",
    "Tuʻi Tonga Empire",
}

NAME_JA = {
    "Denmark-Norway": "デンマーク＝ノルウェー", "Kyivan Rus": "キエフ大公国",
    "Volga Bulgars": "ヴォルガ・ブルガール", "Byzantine Empire": "ビザンツ帝国(東ローマ帝国)",
    "Holy Roman Empire": "神聖ローマ帝国", "Caliphate of Córdoba": "後ウマイヤ朝(コルドバ・カリフ国)",
    "Kingdom of France": "フランス王国", "Poland": "ポーランド公国",
    "Bulgar Khanate": "ブルガリア帝国(第一次)", "Sweden": "スウェーデン王国",
    "Icelandic Commonwealth": "アイスランド共和国", "León": "レオン王国",
    "Burgandy": "ブルゴーニュ公国", "Scotland": "スコットランド王国",
    "Pomerania": "ポメラニア公国", "Duchy of Swabia": "シュヴァーベン公国",
    "Castilla": "カスティーリャ伯領", "Serbia": "セルビア(ラシュカ)",
    "Navarre": "ナバラ王国", "Croatia": "クロアチア王国",
    "Dutchy of Benevento": "ベネヴェント公国", "Britany": "ブルターニュ公国",
    "Emirate of Sicily": "シチリア首長国(イスラム)", "Sardinia": "サルデーニャ諸侯国",
    "Aragón": "アラゴン王国", "Corsica": "コルシカ(ジェノヴァ/ピサ領)",
    "Cyprus": "キプロス(ビザンツ領)", "Venice": "ヴェネツィア共和国",
    "Magyars": "マジャル人(ハンガリー建国前)", "Khazars": "ハザール・カガン国",
    "Peshemegs": "ペチェネグ族", "Kimek-Kipchak khaganate": "キマク・キプチャク・カガン国",
    "England": "イングランド王国",
    "Fatimid Caliphate": "ファーティマ朝(エジプト)", "Makkura": "マクリア王国(ヌビア)",
    "Madagascar": "マダガスカル", "Alwa": "アルワ王国",
    "Great Zimbabwe": "グレート・ジンバブエ王国", "Kanem": "カネム帝国",
    "Ghana": "ガーナ帝国", "Takrur": "タクルール王国",
    "Tiahuanaco Empire": "ティワナク帝国", "Huari Empire": "ワリ帝国",
    "Chimú Empire": "チムー王国", "Toltec Empire": "トルテカ帝国",
    "Tibet": "チベット", "Buwayhid Emirates": "ブワイフ朝(イラク)",
    "Buyid Emirate": "ブワイフ朝(ペルシア)", "Rajput kingdoms": "ラージプート諸王国",
    "Ghaznavid Emirate": "ガズナ朝", "Chalukya Empire": "チャールキヤ朝",
    "Palas": "パーラ朝(ベンガル)", "Chola state": "チョーラ朝",
    "Pratiharas": "プラティーハーラ朝", "Kingdom of Georgia": "グルジア王国",
    "Armenia": "アルメニア王国", "Chauhans": "チャハマーナ朝(チャウハーン朝)",
    "Yemen": "イエメン", "Muscat": "マスカット(オマーン)", "Orissa": "オリッサ王国",
    "Shirvan": "シルヴァン・シャー国", "Kalinga": "カリンガ王国",
    "Song Empire": "宋", "Liao": "遼(契丹)", "Xixia": "西夏",
    "Srivijaya Empire": "シュリーヴィジャヤ王国", "Khmer Empire": "クメール帝国",
    "Imperial Japan (Fujiwara)": "日本(平安時代)", "Kingdom of Pagan": "パガン王朝(ビルマ)",
    "Korea": "高麗(朝鮮)", "East Java": "ジャワ(クディリ王国)", "Annam": "大越(アンナン)",
    "Champa": "チャンパ王国", "Haripunjaya": "ハリプンチャイ王国",
    "Dvaravati": "ドヴァーラヴァティー(モン族)",
    "Tuʻi Tonga Empire": "トゥイ・トンガ帝国",
}

# 地域モード用の区分。
REGIONS = {
    "europe": [
        "Denmark-Norway", "Kyivan Rus", "Volga Bulgars", "Byzantine Empire",
        "Holy Roman Empire", "Caliphate of Córdoba", "Kingdom of France",
        "Poland", "Bulgar Khanate", "Sweden", "Icelandic Commonwealth",
        "León", "Burgandy", "Scotland", "Pomerania", "Duchy of Swabia",
        "Castilla", "Serbia", "Navarre", "Croatia", "Dutchy of Benevento",
        "Britany", "Emirate of Sicily", "Sardinia", "Aragón", "Corsica",
        "Cyprus", "Venice", "Magyars", "Khazars", "Peshemegs",
        "Kimek-Kipchak khaganate", "England",
    ],
    "africa": [
        "Fatimid Caliphate", "Makkura", "Madagascar", "Alwa",
        "Great Zimbabwe", "Kanem", "Ghana", "Takrur",
    ],
    "americas": [
        "Tiahuanaco Empire", "Huari Empire", "Chimú Empire", "Toltec Empire",
    ],
    "wsasia": [
        "Tibet", "Buwayhid Emirates", "Buyid Emirate", "Rajput kingdoms",
        "Ghaznavid Emirate", "Chalukya Empire", "Palas", "Chola state",
        "Pratiharas", "Kingdom of Georgia", "Armenia", "Chauhans", "Yemen",
        "Muscat", "Orissa", "Shirvan", "Kalinga",
    ],
    "easia": [
        "Song Empire", "Liao", "Xixia", "Srivijaya Empire", "Khmer Empire",
        "Imperial Japan (Fujiwara)", "Kingdom of Pagan", "Korea", "East Java",
        "Annam", "Champa", "Haripunjaya", "Dvaravati",
    ],
    "oceania": [
        "Tuʻi Tonga Empire",
    ],
}
COUNTRY_REGIONS = {}
for region, names in REGIONS.items():
    for n in names:
        COUNTRY_REGIONS.setdefault(n, []).append(region)

# 地図上のラベル用の短縮表記(長すぎてピース内に収まらない名前だけ上書き)
LABEL_JA_SHORT = {
    "Denmark-Norway": "デンマーク＝ノルウェー", "Kyivan Rus": "キエフ大公国",
    "Caliphate of Córdoba": "後ウマイヤ朝", "Bulgar Khanate": "ブルガリア帝国",
    "Icelandic Commonwealth": "アイスランド", "Duchy of Swabia": "シュヴァーベン公国",
    "Dutchy of Benevento": "ベネヴェント公国", "Emirate of Sicily": "シチリア首長国",
    "Magyars": "マジャル人", "Kimek-Kipchak khaganate": "キマク・キプチャク",
    "Fatimid Caliphate": "ファーティマ朝", "Makkura": "マクリア王国",
    "Great Zimbabwe": "ジンバブエ", "Tiahuanaco Empire": "ティワナク帝国",
    "Buwayhid Emirates": "ブワイフ朝(イラク)", "Buyid Emirate": "ブワイフ朝(ペルシア)",
    "Rajput kingdoms": "ラージプート", "Chalukya Empire": "チャールキヤ朝",
    "Palas": "パーラ朝", "Pratiharas": "プラティーハーラ朝",
    "Kingdom of Georgia": "グルジア王国", "Chauhans": "チャウハーン朝",
    "Imperial Japan (Fujiwara)": "日本(平安)", "Kingdom of Pagan": "パガン王朝",
    "Srivijaya Empire": "シュリーヴィジャヤ", "Khmer Empire": "クメール帝国",
    "East Java": "クディリ王国", "Haripunjaya": "ハリプンチャイ王国",
    "Dvaravati": "ドヴァーラヴァティー", "Tuʻi Tonga Empire": "トンガ帝国",
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
    src = json.load(open(os.path.join(BASE, "world_1000.geojson"), encoding="utf-8"))
    feats = src["features"]

    named = defaultdict(list)  # name -> list of raw MultiPolygon coordinate lists
    named_props = {}
    all_shapes = []

    for f in feats:
        name = f["properties"].get("NAME")
        coords = f["geometry"]["coordinates"]  # 全featureがMultiPolygon
        if name:
            named[name].append(coords)
            named_props[name] = f["properties"]
        all_shapes.append(shape(f["geometry"]))

    missing_ja = []
    countries_out = []
    excluded_polygons = []  # 採用しなかった領域も陸地としては背景に残す
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

    # NAMEなしのfeatureは元々存在しない(このデータセットは全featureにNAMEがある)。
    # 不採用の国はすべて excluded_polygons に入っている。
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

    # 統合ページ(world-history-puzzle)の data/1100.json に直接出力する
    out_dir = os.path.join(BASE, "..", "..", "data")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "1000.json")
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
