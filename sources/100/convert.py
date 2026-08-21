"""
100年の世界地図(aourednik/historical-basemaps由来のGeoJSON)を読み込み、
経緯度(lon/lat)を正距円筒図法でx,yに投影して、統合ページ用データ
(../../data/100.json)に変換する。

このデータセットは84件と中規模。実在した国家・王国だけを選ぶ
「採用リスト方式」にする。

100年はローマ帝国が五賢帝時代の直前(トラヤヌス帝の即位は98年)、
まだダキア王国(トラヤヌスによる征服は106年)やナバテア王国(併合は
106年)が健在。パルティア帝国・後漢もそれぞれ健在。クシャーナ朝は
建国・拡大期。朝鮮半島は高句麗が確立している一方、百済・新羅・加耶は
馬韓・辰韓・弁韓(三韓)の小国連合段階。

「Yayoi(弥生)」表記の領域は日本列島を指すが、これは考古学的な時代区分
名であり特定の政体を意味しない。実際この時代の日本列島は倭国大乱以前で
「分かれて百余国」(漢書地理志)と評されるほど政治的に統一されておらず、
特定の一国として代表させることが適切でないため不採用とする(統一された
政体としての日本は他年代のデータで「大和」等として別途収録済み)。

「Scythians」表記の領域はbbox確認の結果クリミア半島を指しており、古典期
スキタイの故地は既に失われていたが、クリミア半島に残存したスキタイ人の
王国(いわゆる「小スキタイ」、3世紀まで存続)を指すとみなして採用する。

年代的に不適切と判断し不採用としたもの:
- Dumonii(ブリテン島南西部の部族名だが、100年時点ではローマ帝国の
  属州民でありローマ帝国の領域と重複する)

このデータセットには南米の帝国級エンティティや太平洋の政体が収録
されていないため、南北アメリカ・オセアニア両モードは0件で自動非表示
になる(200年以降と同様)。またNAME未設定のfeatureが非常に多数
(南極大陸・サハラ砂漠内陸部・シベリア内陸部・グリーンランドなど
無所属の広大な陸地)あり、操作不可の背景landとして描画する。

- 同名の複数featureは1つの国(MultiPolygon)にまとめる
- 日付変更線問題は「最大の一塊(陸地)」のbboxを当たり判定・ラベル位置の基準にする
- 採用しなかった領域(NAME未設定の無所属地域を含む)は操作不可の背景landとして残す
- 全ランド(採用+非採用)をshapelyでunionし、外周(海岸線)だけを抽出してoutlineとする
"""
import json
import math
import os
from collections import defaultdict

from shapely.geometry import shape
from shapely.ops import unary_union

BASE = os.path.dirname(__file__)

# 実在した国家・王国のみを採用(84件中27件)。
INCLUDE_NAMES = {
    "Roman Empire", "Alans", "Armenia", "Dacia", "Scythians", "Boihaenum",
    "Bosporian Kingdom",
    "Meroe", "Axum",
    "Parthian Empire", "Saka Kingdom", "Suren Kingdom", "Kushan Empire",
    "Satavahanihara", "Himyarite Kingdom", "Kalinga", "Nabatean Kingdom",
    "Hadramaut", "Simhala",
    "Han", "Southern Xiongnu", "Koguryo", "Yueban", "Silla", "Paekche",
    "Arakan", "Gaya",
}

NAME_JA = {
    "Roman Empire": "ローマ帝国(五賢帝時代)", "Alans": "アラン人(カフカス方面)",
    "Armenia": "アルメニア王国", "Dacia": "ダキア王国",
    "Scythians": "スキタイ(クリミア残存王国)",
    "Boihaenum": "マルコマンニ王国(ボイオハエムム)",
    "Bosporian Kingdom": "ボスポロス王国",
    "Meroe": "メロエ王国(クシュ王国)", "Axum": "アクスム王国",
    "Parthian Empire": "パルティア帝国", "Saka Kingdom": "西クシャトラパ朝(サカ族)",
    "Suren Kingdom": "スレーン家領(シースターン)", "Kushan Empire": "クシャーナ朝",
    "Satavahanihara": "サータヴァーハナ朝",
    "Himyarite Kingdom": "ヒムヤル王国(イエメン)", "Kalinga": "カリンガ王国",
    "Nabatean Kingdom": "ナバテア王国", "Hadramaut": "ハドラマウト王国",
    "Simhala": "シンハラ王国(アヌラーダプラ)",
    "Han": "後漢", "Southern Xiongnu": "南匈奴", "Koguryo": "高句麗",
    "Yueban": "悦般(北匈奴残存勢力)", "Silla": "新羅(斯盧国期)",
    "Paekche": "百済(馬韓諸国期)", "Arakan": "アラカン王国(ヴェーサリー朝)",
    "Gaya": "加耶諸国(弁韓期)",
}

# 地域モード用の区分。このデータセットには南米の帝国級エンティティや
# 太平洋の政体が存在しないため、americas・oceaniaキーは意図的に用意
# していない(0件のモードボタンはゲーム側で自動非表示)。
REGIONS = {
    "europe": [
        "Roman Empire", "Alans", "Armenia", "Dacia", "Scythians",
        "Boihaenum", "Bosporian Kingdom",
    ],
    "africa": [
        "Meroe", "Axum",
    ],
    "wsasia": [
        "Parthian Empire", "Saka Kingdom", "Suren Kingdom", "Kushan Empire",
        "Satavahanihara", "Himyarite Kingdom", "Kalinga", "Nabatean Kingdom",
        "Hadramaut", "Simhala",
    ],
    "easia": [
        "Han", "Southern Xiongnu", "Koguryo", "Yueban", "Silla", "Paekche",
        "Arakan", "Gaya",
    ],
}
COUNTRY_REGIONS = {}
for region, names in REGIONS.items():
    for n in names:
        COUNTRY_REGIONS.setdefault(n, []).append(region)

# 地図上のラベル用の短縮表記(長すぎてピース内に収まらない名前だけ上書き)
LABEL_JA_SHORT = {
    "Roman Empire": "ローマ帝国", "Alans": "アラン人",
    "Scythians": "スキタイ(クリミア)", "Boihaenum": "マルコマンニ王国",
    "Meroe": "メロエ王国", "Saka Kingdom": "西クシャトラパ朝",
    "Suren Kingdom": "スレーン家領", "Himyarite Kingdom": "ヒムヤル王国",
    "Yueban": "悦般", "Paekche": "百済", "Arakan": "アラカン王国",
    "Gaya": "加耶諸国",
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
    src = json.load(open(os.path.join(BASE, "world_100.geojson"), encoding="utf-8"))
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
        if name:
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

    # 統合ページ(world-history-puzzle)の data/100.json に直接出力する
    out_dir = os.path.join(BASE, "..", "..", "data")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "100.json")
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
