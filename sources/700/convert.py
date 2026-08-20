"""
700年の世界地図(aourednik/historical-basemaps由来のGeoJSON)を読み込み、
経緯度(lon/lat)を正距円筒図法でx,yに投影して、統合ページ用データ
(../../data/700.json)に変換する。

このデータセットは128件と中規模。実在した国家・王国・首長国だけを選ぶ
「採用リスト方式」にする。

700年はウマイヤ朝の最盛期に近い時代(まだイベリア半島は西ゴート王国領で
未征服=征服は711年)。フランク王国はメロヴィング朝の「怠惰王」時代で、
ネウストリア・アウストラシアなど複数の副王国に事実上分裂。ビザンツ帝国
(データ上はEastern Roman Empire表記)も健在。イングランドはケント王国
(Cantia)とドゥムノニア王国(コーンウォール)のみがデータに含まれる
(他のヘプターキー諸国はこの年のデータセットには個別収録されていない)。
唐はデータ上「Sui Empire(隋)」と表記されているが、隋は618年に滅亡済み
であり、700年時点で該当領域を実効支配していたのは唐(武周期、則天武后の
治世)であるため、便宜上「唐」として採用する。同様に「Koguryo」表記の
領域も高句麗自体は668年に滅亡済みだが、698年に建国されたばかりの渤海
(旧高句麗遺民による後継国家)を指すとみなし「渤海(建国期)」として採用。
一方「Sasanian Empire」「Sasanian dependencies」はサーサーン朝がすでに
651年に滅亡しており、700年当時は同地域もウマイヤ朝の実効支配下にあった
ため(=Umayyad Caliphateとして別途採用済み)、この2件は年代的に不適切と
判断し不採用(背景landとして残す)。同様の理由で成立年代が明確に700年
より後の「Nan-Zhao(南詔統一は738年)」「Mataram(マタラム王国建国は
732年)」「Palas(パーラ朝成立は8世紀半ば)」も不採用とする。

なお、このデータセットには太平洋の政体が一切収録されていないため、
オセアニアの地域モードは0件になる(ゲーム側で0件モードは自動的に
非表示にする対応済み)。また「NAME未設定」のfeatureが多数(南極大陸・
サハラ砂漠内陸部・シベリア内陸部・グリーンランドなど無所属の広大な陸地)
あり、800年と同様に操作不可の背景landとして描画する。

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

# 実在した国家・王国・首長国のみを採用(128件中53件)。
INCLUDE_NAMES = {
    "Eastern Roman Empire", "Frankish Kingdom", "Neustria",
    "Lombard principalities", "Visigothic Kingdom", "Danube Bulgars",
    "Khazars", "Avars", "Magyars", "Swedes", "Danes", "Saxons", "Frisians",
    "Cantia", "Dumnonia", "Georgian Kingdom", "Armenia", "Cuacasian Albania",
    "Axum", "Empire of Ghana", "Makkura", "Alwa", "Nobatia",
    "Tiahuanaco Empire", "Huari Empire",
    "Umayyad Caliphate", "Tufan Empire", "Western Gokturk Khaganate",
    "Karluks", "Chalukyas", "Kanauj", "Kingdom of Sind", "Maitraka Kingdom",
    "Kingdom of Kapisa", "Kingdom of Kashmir", "Kwarezm",
    "Kingdom of Zunbil", "Mazun", "Pallavas", "Chauhans", "Cheras",
    "Cholas", "Western Gangas", "Pandyas", "Simhala",
    "Sui Empire", "Göktürks", "Koguryo", "Yamato", "Silla", "Chen-La",
    "Champa", "Dvaravati",
}

NAME_JA = {
    "Eastern Roman Empire": "東ローマ帝国(ビザンツ帝国)",
    "Frankish Kingdom": "フランク王国(メロヴィング朝)",
    "Neustria": "ネウストリア(西フランク)",
    "Lombard principalities": "ランゴバルド王国・南イタリア諸公国",
    "Visigothic Kingdom": "西ゴート王国", "Danube Bulgars": "ブルガリア帝国(第一次)",
    "Khazars": "ハザール・カガン国", "Avars": "アヴァール可汗国",
    "Magyars": "マジャル人(ハンガリー建国前)", "Swedes": "スウェーデン(スヴェア人)",
    "Danes": "デンマーク(デーン人)", "Saxons": "ザクセン人(独立部族連合)",
    "Frisians": "フリース人(フリースラント)", "Cantia": "ケント王国",
    "Dumnonia": "ドゥムノニア王国(コーンウォール)",
    "Georgian Kingdom": "グルジア(ジョージア)諸公国", "Armenia": "アルメニア",
    "Cuacasian Albania": "カフカス・アルバニア",
    "Axum": "アクスム王国", "Empire of Ghana": "ガーナ帝国",
    "Makkura": "マクリア王国(ヌビア)", "Alwa": "アルワ王国",
    "Nobatia": "ノバティア王国(ヌビア)",
    "Tiahuanaco Empire": "ティワナク帝国", "Huari Empire": "ワリ帝国",
    "Umayyad Caliphate": "ウマイヤ朝", "Tufan Empire": "吐蕃(チベット帝国)",
    "Western Gokturk Khaganate": "西突厥",
    "Karluks": "カルルク族", "Chalukyas": "チャールキヤ朝",
    "Kanauj": "カナウジ王国", "Kingdom of Sind": "シンド王国",
    "Maitraka Kingdom": "マイトラカ朝(ヴァラビー王国)",
    "Kingdom of Kapisa": "カーピシー王国",
    "Kingdom of Kashmir": "カシミール王国(カルコータ朝)",
    "Kwarezm": "ホラズム", "Kingdom of Zunbil": "ザーブリスターン(ズンビール朝)",
    "Mazun": "マズーン(オマーン)", "Pallavas": "パッラヴァ朝",
    "Chauhans": "チャハマーナ朝(チャウハーン朝)", "Cheras": "チェーラ朝",
    "Cholas": "チョーラ朝", "Western Gangas": "西ガンガ朝",
    "Pandyas": "パーンディヤ朝", "Simhala": "シンハラ王国(アヌラーダプラ)",
    "Sui Empire": "唐", "Göktürks": "突厥(東突厥第二可汗国)",
    "Koguryo": "渤海(建国期、旧高句麗遺民)",
    "Yamato": "日本(大和・飛鳥時代末期)", "Silla": "新羅",
    "Chen-La": "チェンラ王国(真臘)", "Champa": "チャンパ王国",
    "Dvaravati": "ドヴァーラヴァティー王国",
}

# 地域モード用の区分。このデータセットには太平洋の政体が存在しないため
# oceaniaキーは意図的に用意していない(0件のモードボタンはゲーム側で自動非表示)。
REGIONS = {
    "europe": [
        "Eastern Roman Empire", "Frankish Kingdom", "Neustria",
        "Lombard principalities", "Visigothic Kingdom", "Danube Bulgars",
        "Khazars", "Avars", "Magyars", "Swedes", "Danes", "Saxons",
        "Frisians", "Cantia", "Dumnonia", "Georgian Kingdom", "Armenia",
        "Cuacasian Albania",
    ],
    "africa": [
        "Axum", "Empire of Ghana", "Makkura", "Alwa", "Nobatia",
    ],
    "americas": [
        "Tiahuanaco Empire", "Huari Empire",
    ],
    "wsasia": [
        "Umayyad Caliphate", "Tufan Empire", "Western Gokturk Khaganate",
        "Karluks", "Chalukyas", "Kanauj", "Kingdom of Sind",
        "Maitraka Kingdom", "Kingdom of Kapisa", "Kingdom of Kashmir",
        "Kwarezm", "Kingdom of Zunbil", "Mazun", "Pallavas", "Chauhans",
        "Cheras", "Cholas", "Western Gangas", "Pandyas", "Simhala",
    ],
    "easia": [
        "Sui Empire", "Göktürks", "Koguryo", "Yamato", "Silla", "Chen-La",
        "Champa", "Dvaravati",
    ],
}
COUNTRY_REGIONS = {}
for region, names in REGIONS.items():
    for n in names:
        COUNTRY_REGIONS.setdefault(n, []).append(region)

# 地図上のラベル用の短縮表記(長すぎてピース内に収まらない名前だけ上書き)
LABEL_JA_SHORT = {
    "Eastern Roman Empire": "東ローマ帝国", "Frankish Kingdom": "フランク王国",
    "Lombard principalities": "ランゴバルド諸公国", "Danube Bulgars": "ブルガリア帝国",
    "Magyars": "マジャル人", "Dumnonia": "ドゥムノニア王国",
    "Georgian Kingdom": "グルジア諸公国",
    "Maitraka Kingdom": "マイトラカ朝", "Kingdom of Kashmir": "カシミール王国",
    "Kingdom of Zunbil": "ザーブリスターン", "Chauhans": "チャウハーン朝",
    "Koguryo": "渤海(建国期)", "Yamato": "日本(飛鳥時代末期)",
    "Chen-La": "チェンラ王国", "Dvaravati": "ドヴァーラヴァティー",
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
    src = json.load(open(os.path.join(BASE, "world_700.geojson"), encoding="utf-8"))
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

    # 統合ページ(world-history-puzzle)の data/700.json に直接出力する
    out_dir = os.path.join(BASE, "..", "..", "data")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "700.json")
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
