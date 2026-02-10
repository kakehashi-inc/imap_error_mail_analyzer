"""Central category registry for bounce error classification.

All category definitions live here. Other modules import from this file
to ensure consistency when adding, removing, or renaming categories.

Each category entry contains:
    description : str  -- Japanese description for documentation/display.
    prompt      : str  -- English description injected into the Ollama prompt.
    excluded    : bool -- If True the category is excluded from target reports
                          (not actionable by the sender).
"""

CATEGORIES = {
    "ip_block": {
        "description": "送信サーバーIP/ホストのブロックリスト登録",
        "prompt": ("Sending server IP/host blocked on blocklist" " (Spamhaus, RBL, DNSBL, blacklist)"),
        "excluded": False,
    },
    "domain_block": {
        "description": "送信ドメインのブロック・ポリシー拒否",
        "prompt": "Sending domain blocked or rejected by recipient policy",
        "excluded": False,
    },
    "sender_throttle": {
        "description": "送信制限超過・スパムスロットリング・接続数超過",
        "prompt": ("Sending rate/volume limits exceeded," " spam throttling, too many connections"),
        "excluded": False,
    },
    "server_error": {
        "description": "送信側サーバー停止・ディスク容量・TLS/証明書・内部エラー",
        "prompt": ("Sending server down, disk full," " TLS/certificate issues, internal server error"),
        "excluded": False,
    },
    "config_error": {
        "description": "DNS設定不備(SPF/DKIM/DMARC)・リレー拒否・ネットワーク/ルーティング",
        "prompt": ("DNS misconfiguration (SPF/DKIM/DMARC)," " relay denied (sending server not authorized to relay)," " network/routing problems"),
        "excluded": False,
    },
    "user_unknown": {
        "description": "宛先不明・存在しないアドレス・宛先ドメインのタイポ/DNS解決失敗",
        "prompt": ("Wrong/nonexistent recipient address," " recipient domain typo or not found"),
        "excluded": True,
    },
    "user_mailbox_full": {
        "description": "宛先メールボックスの容量超過",
        "prompt": "Recipient mailbox over quota / storage full",
        "excluded": True,
    },
    "user_rate_limit": {
        "description": "受信者側のレート制限",
        "prompt": ("Recipient is receiving mail at a rate" " that prevents delivery (recipient-side rate limit)"),
        "excluded": True,
    },
}

VALID_CATEGORIES = set(CATEGORIES)
EXCLUDED_CATEGORIES = {k for k, v in CATEGORIES.items() if v["excluded"]}
TARGET_CATEGORIES = VALID_CATEGORIES - EXCLUDED_CATEGORIES


def is_excluded_category(category):
    """Return True if *category* is excluded from target reports."""
    return CATEGORIES.get(category, {}).get("excluded", False)


def build_prompt_category_lines():
    """Build the category list block for the Ollama classification prompt.

    Returns a multi-line string like::

        - ip_block : Sending server IP/host blocked ...
        - domain_block : Sending domain blocked ...
    """
    return "\n".join(f"- {key} : {info['prompt']}" for key, info in CATEGORIES.items())
