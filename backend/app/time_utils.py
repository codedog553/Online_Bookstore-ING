"""时间工具（UTC+8，中国大陆时间）。

注意：课程项目使用 SQLite + SQLAlchemy，DateTime 字段通常存储 naive datetime。
为避免 tz-aware 写库/序列化带来的兼容问题，本项目统一约定：
- 所有写入数据库的时间戳均为 **中国大陆时间(UTC+8) 语义的 naive datetime**。
- 所有面向用户展示/业务判断的时间也以该语义为准。

这满足你的要求：所有时间使用东八区（UTC/GMT +8.00）。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone


# 固定使用中国大陆时区（UTC+8）
CN_TZ = timezone(timedelta(hours=8))


def now_cn_naive() -> datetime:
    """获取当前中国时间（UTC+8），并返回 naive datetime。

    说明：
    - datetime.now(CN_TZ) 得到 tz-aware 时间；
    - 去掉 tzinfo 后得到 naive 时间，写入 SQLite DateTime 字段更稳定。
    """

    return datetime.now(CN_TZ).replace(tzinfo=None)


def cn_today_ymd() -> str:
    """返回中国日期 YYYYMMDD（用于订单号日期前缀等）。"""

    return now_cn_naive().strftime("%Y%m%d")
