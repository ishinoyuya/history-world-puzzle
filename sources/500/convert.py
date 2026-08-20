"""
500年の世界地図(aourednik/historical-basemaps由来のGeoJSON)を読み込み、
経緯度(lon/lat)を正距円筒図法でx,yに投影して、統合ページ用データ
(../../data/500.json)に変換する。

このデータセットは88件と中規模。実在した国家・王国・首長国だけを選ぶ
「採用リスト方式」にする。

500年は西ローマ帝国滅亡(476年)直後、ゲルマン諸王国(東ゴート・西ゴート・
フランク・ブルグント・ヴァンダル・スエビ)がかつての西ローマ領を分割
統治する時代。東ローマ帝国(ビザンツ)は健在。中国は南北朝時代で、北は
北魏(拓跋部)、南は南斉(データ上は"Jin Empire"表記だが、晋は420年に
滅亡済みで500年当時は南斉(479-502年)の治世であるため実効支配の連続性
から読み替えて採用)。朝鮮半島は高句麗・百済・新羅の三国時代、日本は
大和(古墳時代)。インドはグプタ朝が衰退期。

「Western Roman Empire」表記の領域は、bboxを確認するとイタリアではなく
ブリテン島西部(ウェールズ付近)を指しており、西ローマ帝国そのものでは
なく、ローマ撤退後もローマ的な政治的アイデンティティを保持していた
ブリトン人残存勢力(サブ・ローマ期のブリテン)を表すとみなし、その通りの
名称で採用する。

年代的に不適切と判断し不採用としたもの:
- Tuʻi Tonga Empire(トゥイ・トンガ王朝の伝統的建国年は950年頃)
このデータセットには他に太平洋の政体が存在しないため、オセアニアモードは
自動非表示。またこのデータセットにはHuari Empire・Tiahuanaco Empireの
ような南米の帝国級エンティティが収録されておらず(北米・中南米は
考古学的culture/complex名のみ)、南北アメリカモードも0件になるため
同様に自動非表示。「culture」「complex」等の考古学文化名(Hopewell
Culture、Nazca、Moche、Teotihuacàn等)は政体ではなく文化圏を指す
名称のため、Huari EmpireやTiahuanaco Empireのような明確な政体名との
一貫性を保つため不採用とする。

なお、このデータセットには「NAME未設定」のfeatureが多数(南極大陸・
サハラ砂漠内陸部・シベリア内陸部・グリーンランドなど無所属の広大な陸地)
あり、600年以前と同様に操作不可の背景landとして描画する。

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

# 実在した国家・王国・首長国のみを採用(88件中40件)。
INCLUDE_NAMES = {
    "Eastern Roman Empire", "Ostrogoths", "Visigoths", "Franks", "Burgunds",
    "Sveves", "Turingians", "Saxons", "Anglo-Saxons", "Western Roman Empire",
    "Armorica", "Basks", "Swedes",
    "Axum", "Empire of Ghana", "Makkura", "Vandals",
    "Sasanian Empire", "Gupta Empire", "Himyarite Kingdom", "Vakataka",
    "Kushan Principalities", "Pallavas", "Western Gangas", "Cholas",
    "Cheras", "Pandyas", "Simhala", "Vishnu-Kundins", "Kadambas",
    "Ruanruan", "Jin Empire", "Toba Wei", "Koguryo", "Paekche", "Silla",
    "Yamato", "Funan", "Champa", "Lavo",
}

NAME_JA = {
    "Eastern Roman Empire": "東ローマ帝国(ビザンツ帝国)",
    "Ostrogoths": "東ゴート王国(イタリア)", "Visigoths": "西ゴート王国",
    "Franks": "フランク王国", "Burgunds": "ブルグント王国",
    "Sveves": "スエビ王国(ガリシア)", "Turingians": "テューリンゲン王国",
    "Saxons": "ザクセン人(大陸、独立部族連合)",
    "Anglo-Saxons": "アングロサクソン人(ブリテン島移住期)",
    "Western Roman Empire": "後期ローマ系ブリトン人残存勢力(ウェールズ)",
    "Armorica": "アルモリカ(ブルターニュ移住ブリトン人)",
    "Basks": "バスク人(独立勢力)", "Swedes": "スウェーデン(スヴェア人)",
    "Axum": "アクスム王国", "Empire of Ghana": "ガーナ帝国",
    "Makkura": "マクリア王国(ヌビア)", "Vandals": "ヴァンダル王国(北アフリカ)",
    "Sasanian Empire": "サーサーン朝ペルシア", "Gupta Empire": "グプタ朝(衰退期)",
    "Himyarite Kingdom": "ヒムヤル王国(イエメン)", "Vakataka": "ヴァーカータカ朝",
    "Kushan Principalities": "クシャーノ系諸侯国", "Pallavas": "パッラヴァ朝",
    "Western Gangas": "西ガンガ朝", "Cholas": "チョーラ朝", "Cheras": "チェーラ朝",
    "Pandyas": "パーンディヤ朝", "Simhala": "シンハラ王国(アヌラーダプラ)",
    "Vishnu-Kundins": "ヴィシュヌクンディン朝", "Kadambas": "カダンバ朝",
    "Ruanruan": "柔然", "Jin Empire": "南斉(南朝)", "Toba Wei": "北魏(拓跋部)",
    "Koguryo": "高句麗", "Paekche": "百済", "Silla": "新羅",
    "Yamato": "日本(大和・古墳時代)", "Funan": "扶南", "Champa": "チャンパ王国",
    "Lavo": "ラヴォ王国(ロッブリー)",
}

# 地域モード用の区分。このデータセットには実在する太平洋の政体が存在せず
# (Tuʻi Tonga Empireは年代的に不採用)、また南北アメリカも帝国級の政体が
# 収録されていないため、oceaniaキー・americasキーは意図的に用意していない
# (0件のモードボタンはゲーム側で自動非表示)。
REGIONS = {
    "europe": [
        "Eastern Roman Empire", "Ostrogoths", "Visigoths", "Franks",
        "Burgunds", "Sveves", "Turingians", "Saxons", "Anglo-Saxons",
        "Western Roman Empire", "Armorica", "Basks", "Swedes",
    ],
    "africa": [
        "Axum", "Empire of Ghana", "Makkura", "Vandals",
    ],
    "wsasia": [
        "Sasanian Empire", "Gupta Empire", "Himyarite Kingdom", "Vakataka",
        "Kushan Principalities", "Pallavas", "Western Gangas", "Cholas",
        "Cheras", "Pandyas", "Simhala", "Vishnu-Kundins", "Kadambas",
    ],
    "easia": [
        "Ruanruan", "Jin Empire", "Toba Wei", "Koguryo", "Paekche", "Silla",
        "Yamato", "Funan", "Champa", "Lavo",
    ],
}
COUNTRY_REGIONS = {}
for region, names in REGIONS.items():
    for n in names:
        COUNTRY_REGIONS.setdefault(n, []).append(region)

# 地図上のラベル用の短縮表記(長すぎてピース内に収まらない名前だけ上書き)
LABEL_JA_SHORT = {
    "Eastern Roman Empire": "東ローマ帝国", "Ostrogoths": "東ゴート王国",
    "Western Roman Empire": "ブリトン人残存勢力", "Armorica": "アルモリカ",
    "Anglo-Saxons": "アングロサクソン人", "Himyarite Kingdom": "ヒムヤル王国",
    "Vishnu-Kundins": "ヴィシュヌクンディン朝", "Gupta Empire": "グプタ朝",
    "Jin Empire": "南斉", "Toba Wei": "北魏", "Yamato": "日本(古墳時代)",
    "Lavo": "ラヴォ王国",
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
    src = json.load(open(os.path.join(BASE, "world_500.geojson"), encoding="utf-8"))
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

    # 統合ページ(world-history-puzzle)の data/500.json に直接出力する
    out_dir = os.path.join(BASE, "..", "..", "data")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "500.json")
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
