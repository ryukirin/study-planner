"""看剧换算的预设剧目。

集数按官方来源核对（播出方、出品方或正版平台的页面），source 记录核对用的页面。
每集时长是按这部剧通常的单集长度取的估算值，界面上显示为“约”。
电影用 total_minutes 记录官方页面写的片长（2026-11-14 核对）。
只收单部作品，不收合集。同一部剧的几季可以合成一条。
"""
from __future__ import annotations

from typing import Any

PRESETS: dict[str, dict[str, Any]] = {
    "cn_drama": {
        "name": "国产剧",
        "note": "每集按 45 分钟估算。",
        "shows": [
            {"title": "隐秘的角落", "episodes": 12, "minutes_per_episode": 45, "source": "https://www.iqiyi.com/a_19rrhm0f1d.html"},
            {"title": "繁花", "episodes": 30, "minutes_per_episode": 45, "source": "http://paper.people.com.cn/rmrbhwb/html/2024-01/11/content_26036391.htm"},
            {"title": "父母爱情", "episodes": 44, "minutes_per_episode": 45, "source": "https://tv.cctv.com/2014/01/07/VIDA1389081608990301.shtml"},
            {"title": "琅琊榜", "episodes": 54, "minutes_per_episode": 45, "source": "http://dianshiju.cctv.com/2015/08/31/VIDA1440999745153940.shtml"},
            {"title": "甄嬛传", "episodes": 76, "minutes_per_episode": 45, "source": "http://dianshiju.cctv.com/2013/01/05/VIDA1357379656909389.shtml"},
            {"title": "武林外传", "episodes": 80, "minutes_per_episode": 45, "source": "https://tv.cctv.com/2012/12/03/VIDA1354531513618469.shtml"},
            {"title": "漫长的季节", "episodes": 12, "minutes_per_episode": 45, "source": "https://m.v.qq.com/x/m/play?cid=mzc00200fhhxx8d&vid=j35111c405b"},
            {"title": "山海情", "episodes": 23, "minutes_per_episode": 45, "source": "https://www.iqiyi.com/a_22e55c1zarp.html"},
            {"title": "潜伏", "episodes": 30, "minutes_per_episode": 45, "source": "https://www.iqiyi.com/dianshiju/qf.html"},
            {"title": "狂飙", "episodes": 39, "minutes_per_episode": 45, "source": "https://zgdsb.cctv.com/2023/01/19/ARTIokwnN4hJhrWl2NTfjBTA230119.shtml"},
            {"title": "大明王朝1566", "episodes": 46, "minutes_per_episode": 45, "source": "https://list.youku.com/albumlist/show/id_49948080.html"},
            {"title": "人世间", "episodes": 58, "minutes_per_episode": 45, "source": "https://zgdsb.cctv.com/2022/02/24/ARTI46ckP8kC4SIHgnfyf8K2220224.shtml"},
        ],
    },
    "us_drama": {
        "name": "美剧",
        "note": "每集时长按剧集类型估算，情景喜剧约 20 分钟，正剧约 45 到 60 分钟。",
        "shows": [
            {"title": "切尔诺贝利", "episodes": 5, "minutes_per_episode": 60, "source": "https://www.hbomaxlapress.com/news/667"},
            {"title": "绝命毒师", "episodes": 62, "minutes_per_episode": 47, "source": "https://www.netflix.com/tudum/articles/breaking-bad-best-episodes"},
            {"title": "权力的游戏", "episodes": 73, "minutes_per_episode": 55, "source": "https://www.hbomax.com/tc/en/shows/game-of-thrones/4f6b4985-2dc9-4ab6-ac79-d60f0860b0ac"},
            {"title": "老友记", "episodes": 236, "minutes_per_episode": 22, "source": "https://press.wbd.com/us/media-release/one-where-they-got-back-together"},
            {"title": "生活大爆炸", "episodes": 279, "minutes_per_episode": 20, "source": "https://www.warnerbros.com/studio/news/big-bang-theory-end-2019-longest-running-multi-camera-comedy-series-tv-history"},
            {"title": "兄弟连", "episodes": 10, "minutes_per_episode": 60, "source": "https://www.hbo.com/band-of-brothers"},
            {"title": "继承之战", "episodes": 39, "minutes_per_episode": 60, "source": "https://www.hbomax.com/aw/en/shows/succession/a8484031-f244-4661-9fb7-0932bd1ba872"},
            {"title": "火线", "episodes": 60, "minutes_per_episode": 58, "source": "https://www.hbomax.com/ai/en/shows/wire/1bc3aff5-0d6a-4c0b-8ed0-5716ca30ab3b"},
            {"title": "办公室（美版）", "episodes": 201, "minutes_per_episode": 22, "source": "https://www.nbc.com/nbc-insider/how-to-watch-the-office-episodes"},
        ],
    },
    "jp_drama": {
        "name": "日剧",
        "note": "每集按 46 分钟估算。",
        "shows": [
            {"title": "非自然死亡", "episodes": 10, "minutes_per_episode": 46, "source": "https://www.tbs.co.jp/unnatural2018/story/"},
            {"title": "四重奏", "episodes": 10, "minutes_per_episode": 46, "source": "https://www.tbs.co.jp/quartet2017/story/"},
            {"title": "重版出来！", "episodes": 10, "minutes_per_episode": 46, "source": "https://www.tbs.co.jp/juhan-shuttai/story/"},
            {"title": "陆王", "episodes": 10, "minutes_per_episode": 46, "source": "https://www.tbs.co.jp/rikuou_tbs/story/"},
            {"title": "不適切にもほどがある！", "episodes": 10, "minutes_per_episode": 46, "source": "https://www.tbs.co.jp/futekisetsunimohodogaaru/story/"},
            {"title": "重启人生", "episodes": 10, "minutes_per_episode": 46, "source": "https://www.ntv.co.jp/brushup-life/story/"},
            {"title": "逃避虽可耻但有用", "episodes": 11, "minutes_per_episode": 46, "source": "https://www.tbs.co.jp/NIGEHAJI_tbs/story/"},
            {"title": "MIU404", "episodes": 11, "minutes_per_episode": 46, "source": "https://www.tbs.co.jp/MIU404_TBS/story/"},
            {"title": "仁医（第一季）", "episodes": 11, "minutes_per_episode": 46, "source": "https://www.tbs.co.jp/jin2009/story/"},
            {"title": "东京大饭店", "episodes": 11, "minutes_per_episode": 46, "source": "https://www.tbs.co.jp/grandmaisontokyo/2019/story/"},
            {"title": "最完美的离婚", "episodes": 11, "minutes_per_episode": 46, "source": "https://www.fujitv.co.jp/b_hp/saikouno_rikon/"},
            {"title": "silent", "episodes": 11, "minutes_per_episode": 46, "source": "https://www.fujitv.co.jp/silent/story/"},
            {"title": "半泽直树（2013、2020）", "episodes": 20, "minutes_per_episode": 46, "source": "https://www.tbs.co.jp/hanzawa_naoki/story/"},
        ],
    },
    "kr_drama": {
        "name": "韩剧",
        "note": "每集时长按这部剧通常的长度估算，在 55 到 90 分钟之间。",
        "shows": [
            {"title": "黑暗荣耀", "episodes": 16, "minutes_per_episode": 55, "source": "https://www.netflix.com/title/81519223"},
            {"title": "爱的迫降", "episodes": 16, "minutes_per_episode": 80, "source": "https://www.netflix.com/title/81159258"},
            {"title": "鱿鱼游戏（全三季）", "episodes": 22, "minutes_per_episode": 55, "source": "https://www.netflix.com/title/81040344"},
            {"title": "请回答1988", "episodes": 20, "minutes_per_episode": 90, "source": "https://www.cjenm.com/en/featured-contents/reply-1988/"},
            {"title": "大长今", "episodes": 54, "minutes_per_episode": 60, "source": "https://content.mbc.co.kr/program/drama/2604956_64285.html"},
            {"title": "我的大叔", "episodes": 16, "minutes_per_episode": 75, "source": "https://cjenm.com/en/featured-contents/my-mister/"},
            {"title": "非常律师禹英禑", "episodes": 16, "minutes_per_episode": 70, "source": "https://www.netflix.com/title/81518991"},
            {"title": "鬼怪", "episodes": 16, "minutes_per_episode": 70, "source": "https://www.cjenm.com/en/featured-contents/guardian--the-lonely-and-great-god/"},
            {"title": "信号", "episodes": 16, "minutes_per_episode": 70, "source": "https://www.cjenm.com/en/featured-contents/signal/"},
        ],
    },
    "anime": {
        "name": "动画",
        "note": "每集按 24 分钟估算。",
        "shows": [
            {"title": "新世纪福音战士", "episodes": 26, "minutes_per_episode": 24, "source": "https://www.evangelion.jp/news/neongenesis_tv/"},
            {"title": "钢之炼金术师 FULLMETAL ALCHEMIST", "episodes": 64, "minutes_per_episode": 24, "source": "https://www.aniplex.co.jp/lineup/hagarenfa/news/detail/?id=10177"},
            {"title": "灌篮高手", "episodes": 101, "minutes_per_episode": 24, "source": "https://lineup.toei-anim.co.jp/ja/tv/movie_slumdunk/"},
            {"title": "龙珠", "episodes": 153, "minutes_per_episode": 24, "source": "https://lineup.toei-anim.co.jp/ja/tv/dragon/"},
            {"title": "龙珠Z", "episodes": 291, "minutes_per_episode": 24, "source": "https://lineup.toei-anim.co.jp/ja/tv/dragonz/"},
            {"title": "命运石之门", "episodes": 24, "minutes_per_episode": 24, "source": "https://steinsgate.jp/10th/project8/"},
            {"title": "星际牛仔", "episodes": 26, "minutes_per_episode": 24, "source": "https://www.sunrise-inc.co.jp/work/detail.php?cid=41"},
            {"title": "葬送的芙莉莲（第一季）", "episodes": 28, "minutes_per_episode": 24, "source": "https://frieren-anime.jp/story/1st/"},
        ],
    },
    "girls_band": {
        "name": "少女乐队",
        "note": "每集按 24 分钟估算。",
        "shows": [
            {"title": "孤独摇滚！", "episodes": 12, "minutes_per_episode": 24, "source": "https://www.aniplex.co.jp/lineup/bocchi/news/detail/?id=62212"},
            {"title": "GIRLS BAND CRY", "episodes": 13, "minutes_per_episode": 24, "source": "https://lineup.toei-anim.co.jp/ja/tv/girls-band-cry/episode/"},
            {"title": "BanG Dream! It's MyGO!!!!!", "episodes": 13, "minutes_per_episode": 24, "source": "https://anime.bang-dream.com/mygo/news/post-33"},
            {"title": "BanG Dream! Ave Mujica", "episodes": 13, "minutes_per_episode": 24, "source": "https://anime.bang-dream.com/avemujica/news/post-17"},
            {"title": "BanG Dream!（第一至三季）", "episodes": 39, "minutes_per_episode": 24, "source": "https://bang-dream.com/anime/"},
        ],
    },
    "movie": {
        "name": "电影",
        "note": "片长取官方页面的数字。电影单部较短，累计时长超过最长的一部后显示看了几遍。",
        "shows": [
            {"title": "楚门的世界", "total_minutes": 104, "source": "https://www.paramount.com/movies/the-truman-show"},
            {"title": "壮志凌云：独行侠", "total_minutes": 131, "source": "https://www.paramount.com/movies/top-gun-maverick"},
            {"title": "阿甘正传", "total_minutes": 142, "source": "https://www.paramount.com/movies/forrest-gump"},
            {"title": "角斗士", "total_minutes": 155, "source": "https://www.paramount.com/movies/gladiator"},
            {"title": "星际穿越", "total_minutes": 168, "source": "https://www.paramount.com/movies/interstellar"},
            {"title": "拯救大兵瑞恩", "total_minutes": 170, "source": "https://www.paramount.com/movies/saving-private-ryan"},
            {"title": "教父", "total_minutes": 175, "source": "https://www.paramount.com/movies/the-godfather"},
            {"title": "泰坦尼克号", "total_minutes": 196, "source": "https://www.paramount.com/movies/titanic"},
            {"title": "碟中谍", "total_minutes": 111, "source": "https://www.paramount.com/movies/mission-impossible"},
            {"title": "勇敢的心", "total_minutes": 178, "source": "https://www.paramount.com/movies/braveheart"},
            {"title": "华尔街之狼", "total_minutes": 179, "source": "https://www.paramount.com/movies/the-wolf-of-wall-street"},
            {"title": "教父 2", "total_minutes": 200, "source": "https://www.paramount.com/movies/the-godfather-part-ii"},
        ],
    },
}
