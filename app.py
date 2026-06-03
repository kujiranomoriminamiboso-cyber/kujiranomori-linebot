"""
くじらのもりくん LINE Bot
- 3つの質問で自然体験を診断するルールベースボット
- Python + Flask + LINE Messaging API
"""

import os
from flask import Flask, request, abort
from linebot.v3 import WebhookHandler
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
    FlexMessage,
    FlexContainer,
    QuickReply,
    QuickReplyItem,
    MessageAction,
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
    FollowEvent,
)
from linebot.v3.exceptions import InvalidSignatureError

app = Flask(__name__)

# ===== LINE API 設定 =====
CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET", "")

configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

# ===== ユーザーの回答状態を管理 =====
user_states = {}


# ===== 選択肢の定義 =====
AGE_OPTIONS = [
    ("乳幼児", "baby"),
    ("未就学児", "preschool"),
    ("小学生", "elementary"),
    ("中学生以上", "junior"),
]

LIKE_OPTIONS = [
    ("海あそび", "sea"),
    ("川あそび", "river"),
    ("生き物探し", "creature"),
    ("魚釣り", "fishing"),
    ("キャンプ", "camp"),
    ("工作・クラフト", "craft"),
    ("雪あそび", "snow"),
    ("夜の探検", "night"),
]

SEASON_OPTIONS = [
    ("春", "spring"),
    ("夏", "summer"),
    ("秋", "autumn"),
    ("冬", "winter"),
    ("いつでも", "any"),
]


# ===== ツアーの季節マッピング =====
TOUR_SEASONS = {
    "磯あそび＆海あそび": ["summer"],
    "仁右衛門島 海あそび島編": ["summer"],
    "海の真横で絶景キャンプ！": ["summer"],
    "半日川あそび": ["summer"],
    "川あそび×デイキャンプ": ["summer"],
    "夏休み川キャンプ": ["summer"],
    "釣りとお魚ランチ": ["spring", "summer", "autumn"],
    "初めての船釣り1泊2日": ["spring", "summer", "autumn"],
    "ウミホタル観察": ["summer", "autumn"],
    "夜の川探検": ["summer"],
    "昆虫ナイトハイク": ["summer"],
    "南魚沼雪遊び体験": ["winter"],
    "里山のクリスマスパーティー": ["winter"],
    "新年たこあげ×きりたんぽ鍋": ["winter"],
}


def get_recommendation(age, like, season):
    """HPチャットボットと同じ診断ロジック"""
    title = ""
    tours = []

    if like == "sea":
        title = "海あそびが好きなご家族におすすめ！"
        tours = ["磯あそび＆海あそび", "仁右衛門島 海あそび島編", "海の真横で絶景キャンプ！"]
    elif like == "river":
        title = "川あそびが好きなご家族におすすめ！"
        tours = ["半日川あそび", "川あそび×デイキャンプ", "夏休み川キャンプ"]
    elif like == "creature":
        title = "生き物好きのお子さまにおすすめ！"
        tours = ["磯あそび＆海あそび", "夜の川探検", "昆虫ナイトハイク", "ウミホタル観察"]
    elif like == "fishing":
        title = "魚釣りに挑戦したいご家族におすすめ！"
        tours = ["釣りとお魚ランチ", "初めての船釣り1泊2日"]
    elif like == "camp":
        title = "キャンプを楽しみたいご家族におすすめ！"
        tours = ["夏休み川キャンプ", "海の真横で絶景キャンプ！", "南魚沼雪遊び体験"]
    elif like == "craft":
        title = "工作・クラフト好きにおすすめ！"
        if season in ("winter", "any"):
            tours = ["里山のクリスマスパーティー", "新年たこあげ×きりたんぽ鍋"]
        else:
            tours = []
    elif like == "snow":
        title = "雪あそびを楽しみたいご家族におすすめ！"
        tours = ["南魚沼雪遊び体験"]
    elif like == "night":
        title = "夜の探検を楽しみたいご家族におすすめ！"
        tours = ["ウミホタル観察", "夜の川探検", "昆虫ナイトハイク"]

    # 乳幼児・未就学児は冬イベントを先頭に追加
    if age in ("baby", "preschool"):
        if season in ("winter", "any"):
            tours = ["新年たこあげ×きりたんぽ鍋", "里山のクリスマスパーティー"] + tours

    # 重複を除去（順序を保持）
    seen = set()
    unique_tours = []
    for t in tours:
        if t not in seen:
            seen.add(t)
            unique_tours.append(t)

    # 季節フィルタリング
    if season != "any":
        unique_tours = [
            t for t in unique_tours
            if t not in TOUR_SEASONS or season in TOUR_SEASONS[t]
        ]

    return title, unique_tours


def make_quick_reply(options):
    """クイックリプライボタンを生成"""
    items = [
        QuickReplyItem(action=MessageAction(label=label, text=label))
        for label, _ in options
    ]
    return QuickReply(items=items)


def make_result_flex(title, tours):
    """診断結果のFlexメッセージを生成"""
    tour_list = "\n".join([f"・{t}" for t in tours]) if tours else ""

    if tours:
        contents = {
            "type": "bubble",
            "size": "mega",
            "header": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": f"\U0001F40B {title}",
                        "weight": "bold",
                        "size": "md",
                        "color": "#0b8fa8",
                        "wrap": True,
                    }
                ],
                "backgroundColor": "#f5fbff",
                "paddingAll": "16px",
            },
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": "ご家族には、こちらの体験が合いそうです。",
                        "size": "sm",
                        "wrap": True,
                        "margin": "md",
                    },
                    {
                        "type": "text",
                        "text": tour_list,
                        "size": "sm",
                        "wrap": True,
                        "margin": "lg",
                        "lineSpacing": "8px",
                    },
                    {
                        "type": "text",
                        "text": "\U0001F40B 迷ったらLINEでご相談ください",
                        "size": "xs",
                        "color": "#888888",
                        "wrap": True,
                        "margin": "xl",
                    },
                ],
                "paddingAll": "16px",
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "button",
                        "action": {
                            "type": "uri",
                            "label": "現在申し込み可能な体験一覧",
                            "uri": "https://www.asoview.com/channel/activities/ja/kujiranomori/offices/2356/courses?language_type=ja",
                        },
                        "style": "primary",
                        "color": "#f39800",
                        "height": "sm",
                    },
                    {
                        "type": "button",
                        "action": {
                            "type": "uri",
                            "label": "もう一度診断する",
                            "uri": "https://line.me/R/oaMessage/@kujiranomori/?%E8%A8%BA%E6%96%AD",
                        },
                        "style": "secondary",
                        "height": "sm",
                        "margin": "sm",
                    },
                ],
                "paddingAll": "12px",
            },
            "styles": {
                "header": {"separator": False},
                "footer": {"separator": True},
            },
        }
    else:
        # ツアーが見つからない場合
        contents = {
            "type": "bubble",
            "size": "mega",
            "body": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "text",
                        "text": f"\U0001F40B {title}",
                        "weight": "bold",
                        "size": "md",
                        "color": "#0b8fa8",
                        "wrap": True,
                    },
                    {
                        "type": "text",
                        "text": "選ばれた季節に該当するツアーが見つかりませんでした。\n別の季節や「いつでも」をお試しください。",
                        "size": "sm",
                        "wrap": True,
                        "margin": "lg",
                    },
                ],
                "paddingAll": "16px",
            },
            "footer": {
                "type": "box",
                "layout": "vertical",
                "contents": [
                    {
                        "type": "button",
                        "action": {
                            "type": "uri",
                            "label": "現在申し込み可能な体験一覧",
                            "uri": "https://www.asoview.com/channel/activities/ja/kujiranomori/offices/2356/courses?language_type=ja",
                        },
                        "style": "primary",
                        "color": "#f39800",
                        "height": "sm",
                    },
                ],
                "paddingAll": "12px",
            },
        }

    return contents


def find_value_by_label(options, label):
    """表示名からvalueを取得"""
    for opt_label, opt_value in options:
        if opt_label == label:
            return opt_value
    return None


# ===== Webhook エンドポイント =====
@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return "OK"


@app.route("/health", methods=["GET"])
def health():
    return "OK"


# ===== 友だち追加時 =====
@handler.add(FollowEvent)
def handle_follow(event):
    user_id = event.source.user_id
    user_states[user_id] = {"step": "age"}

    with ApiClient(configuration) as api_client:
        api = MessagingApi(api_client)
        api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[
                    TextMessage(
                        text="こんにちは！くじらのもりくんです\U0001F40B\n\n"
                        "3つの質問で、ご家族に合いそうな自然体験をご紹介します。\n\n"
                        "① お子さまの年齢を選んでください",
                        quick_reply=make_quick_reply(AGE_OPTIONS),
                    )
                ],
            )
        )


# ===== メッセージ受信時 =====
@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()

    # 「診断」「スタート」「はじめる」等で最初から開始
    if text in ("診断", "スタート", "はじめる", "もう一度", "リセット") or user_id not in user_states:
        user_states[user_id] = {"step": "age"}
        with ApiClient(configuration) as api_client:
            api = MessagingApi(api_client)
            api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[
                        TextMessage(
                            text="こんにちは！くじらのもりくんです\U0001F40B\n\n"
                            "3つの質問で、ご家族に合いそうな自然体験をご紹介します。\n\n"
                            "① お子さまの年齢を選んでください",
                            quick_reply=make_quick_reply(AGE_OPTIONS),
                        )
                    ],
                )
            )
        return

    state = user_states[user_id]
    step = state.get("step", "age")

    with ApiClient(configuration) as api_client:
        api = MessagingApi(api_client)

        if step == "age":
            value = find_value_by_label(AGE_OPTIONS, text)
            if not value:
                api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[
                            TextMessage(
                                text="下のボタンから選んでくださいね\U0001F40B",
                                quick_reply=make_quick_reply(AGE_OPTIONS),
                            )
                        ],
                    )
                )
                return
            state["age"] = value
            state["step"] = "like"
            api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[
                        TextMessage(
                            text=f"「{text}」ですね！\n\n② 好きなことを選んでください",
                            quick_reply=make_quick_reply(LIKE_OPTIONS),
                        )
                    ],
                )
            )

        elif step == "like":
            value = find_value_by_label(LIKE_OPTIONS, text)
            if not value:
                api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[
                            TextMessage(
                                text="下のボタンから選んでくださいね\U0001F40B",
                                quick_reply=make_quick_reply(LIKE_OPTIONS),
                            )
                        ],
                    )
                )
                return
            state["like"] = value
            state["step"] = "season"
            api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[
                        TextMessage(
                            text=f"「{text}」が好きなんですね！\n\n③ 参加したい季節を選んでください",
                            quick_reply=make_quick_reply(SEASON_OPTIONS),
                        )
                    ],
                )
            )

        elif step == "season":
            value = find_value_by_label(SEASON_OPTIONS, text)
            if not value:
                api.reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[
                            TextMessage(
                                text="下のボタンから選んでくださいね\U0001F40B",
                                quick_reply=make_quick_reply(SEASON_OPTIONS),
                            )
                        ],
                    )
                )
                return
            state["season"] = value

            # 診断実行
            title, tours = get_recommendation(
                state["age"], state["like"], state["season"]
            )

            flex_contents = make_result_flex(title, tours)

            # 状態をリセット（次回は最初から）
            user_states[user_id] = {"step": "done"}

            api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[
                        FlexMessage(
                            alt_text=f"\U0001F40B {title}",
                            contents=FlexContainer.from_dict(flex_contents),
                        ),
                        TextMessage(
                            text="もう一度診断したい場合は「診断」と送ってくださいね\U0001F40B"
                        ),
                    ],
                )
            )

        else:
            # 診断済み → 再スタートを促す
            user_states[user_id] = {"step": "age"}
            api.reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[
                        TextMessage(
                            text="くじらのもりくんです\U0001F40B\n\n"
                            "もう一度診断しますね！\n\n"
                            "① お子さまの年齢を選んでください",
                            quick_reply=make_quick_reply(AGE_OPTIONS),
                        )
                    ],
                )
            )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
