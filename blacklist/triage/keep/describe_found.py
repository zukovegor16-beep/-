#!/usr/bin/env python3
"""Build per-URL can/cannot notes from repo names. Code was never executed."""
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent

PREAMBLE = """# Что заявлено и чего нет (keep)

Код **не запускали**. «Может» = заявка в имени репозитория + страница GitHub когда-то открывалась (HTTP 200).
Это **не** проверка, что скрипт работает, не пустой и не подмена (в этой кампании ZIP иногда стилер).

Общее «нет» для любой записи ниже:
- не официальный продукт OpenAI / Cursor / Composio;
- не качалка TikTok / Instagram / SoundCloud (кроме отдельных live/API-обёрток);
- не рассылка VK / TikTok / OK / Avito;
- не дамп киносайтов;
- не минус-список из миллионов доменов (`../../MINUS-LIST.md`).

Кряки, no-trial, стилеры, массовые рассылки, RAT/инжект/брут **не расписываю по возможностям** — только отсылка к сырому файлу.

"""

SKIP_SOFT = (
    "rat", "inject", "bypass", "brute", "exploit", "checker", "cvv",
    "payload", "spoofer", "uac-", "quasar", "hackingtool", "burpinject",
    "wordpress-bruter", "activation-toolkit", "freezer", "kexploit",
)

PARSER_SPEC = {
    "flarecrawl": (
        "универсальный краулер страниц (движок «открой URL — забери HTML»).",
        "не заточен под один магазин/соцсеть; сам по себе не даёт таблицу Amazon или фолловеров Instagram.",
    ),
    "AI-OSINT-Security-Analyzer": (
        "OSINT-набор: по имени анализ открытых данных / «безопасность».",
        "не парсер одного магазина; не рассылка.",
    ),
    "how-to-scrape-google-images-with-python": (
        "забрать картинки из Google Images скриптом.",
        "не видео, не фолловеры соцсетей, не отзывы магазинов.",
    ),
    "__2025_07_08_tvdi_crawler__": (
        "краулер с мусорным/учебным именем (tvdi); цель сайта по имени неясна.",
        "непонятно, какой сайт; не универсальный «парсь всё».",
    ),
    "release-extractor": (
        "вытащить данные из «release» (релизы/файлы), не витрина магазина.",
        "не скрейпер Amazon/LinkedIn.",
    ),
    "blueosint": (
        "OSINT-комбайн по открытым источникам.",
        "не один целевой сайт; не mailer.",
    ),
    "YouTube-Summary-Scraper": (
        "забрать/пересказать текст ролика YouTube.",
        "не качалка файла видео (это другая коробка); не почта из описаний — для почты есть отдельный youtube-email-scraper.",
    ),
    "myntra-reviews-scraper": (
        "отзывы магазина Myntra.",
        "не Amazon, не G2, не LinkedIn.",
    ),
    "linkedin-job-scraper": (
        "вакансии LinkedIn.",
        "не Sales Navigator (это другой репо); не рассылка по найденным людям.",
    ),
    "IscrapeMDB": (
        "скрейп MDB (по имени — база вроде IMDb/Movie).",
        "не соцсети и не интернет-магазин одежды.",
    ),
    "tubescrape": (
        "скрейп видео/YouTube-подобных страниц.",
        "не качалка mp4; не Instagram.",
    ),
    "facebook-events-scraper": (
        "события Facebook.",
        "не маркетплейс, не список друзей (фолловеры — другой репо).",
    ),
    "immobiliare-it-listing-page-scraper-by-search-url": (
        "объявления жилья Immobiliare.it по URL поиска.",
        "не Avito, не авто Autoscout.",
    ),
    "facebook-followers-following-scraper-fast-cheap": (
        "список подписок/подписчиков Facebook.",
        "не Instagram followers; не рассылка им в личку.",
    ),
    "webscraper-to-identify-which-girls-and-how-many-of-them-my-boyfriend-follows-on-GitHub": (
        "шуточный/узкий скрейпер подписок на GitHub.",
        "не Facebook/Instagram; не OSINT-комбайн.",
    ),
    "TotalOSINT": (
        "пачка OSINT-инструментов.",
        "не парсер одного магазина.",
    ),
    "CoSINT": (
        "OSINT-набор.",
        "не скрейпер конкретного шопа.",
    ),
    "LongParser": (
        "парсер с неясной целью (длинный текст/лог?).",
        "сайт-цель по имени не видна.",
    ),
    "markdown-ui-dsl": (
        "скорее разбор markdown/DSL интерфейса, не чужой сайт.",
        "не заберёт карточки Amazon; в коробке парсеров по слову parser/scrape слабо.",
    ),
    "video-scraping-apis": (
        "API/скрейп метаданных видео.",
        "не обязательно качает файл; не TikTok-качалка.",
    ),
    "Savills-Auction-Data-Scraper": (
        "лоты аукциона Savills.",
        "не Immobiliare, не Avito.",
    ),
    "autoscout24-germany-deutschland-scraper": (
        "объявления авто AutoScout24 (Германия).",
        "не жильё, не Amazon.",
    ),
    "scraped": (
        "имя слишком общее: «что-то скрейпили».",
        "цель сайта неизвестна.",
    ),
    "divessi-padi-divesite-catalog-scraper": (
        "каталог дайв-сайтов (PADI/Divi).",
        "не магазины одежды.",
    ),
    "Web-Scraper-for-E-commerce": (
        "общий скрейпер интернет-магазина (карточки/цены).",
        "не заточен под Amazon/Myntra по имени.",
    ),
    "scraping-browser": (
        "браузерный движок скрейпа (обход «как человек»).",
        "сам без цели сайта; не таблица конкретного шопа.",
    ),
    "scrape-rs": (
        "универсальный скрейпер на Rust.",
        "не привязан к одной площадке.",
    ),
    "amazon-scraper": (
        "карточки Amazon.",
        "не отзывы с фильтрами (это amazon-reviews-…); не Myntra.",
    ),
    "partnershipparser": (
        "парсер партнёрок/partnership-страниц.",
        "не витрина товаров.",
    ),
    "librecrawl-mcp": (
        "краулер, ещё и как MCP к модели.",
        "не скил «нарисуй сайт»; не mailer.",
    ),
    "-Discord-OSINT-Transform-for-Maltego": (
        "OSINT по Discord в Maltego.",
        "не парсер магазина; не Discord-рассылка.",
    ),
    "g2-reviews-scraper": (
        "отзывы G2.",
        "не Amazon, не Google News.",
    ),
    "Brahmastra_OSINT": (
        "OSINT-комбайн.",
        "не один сайт.",
    ),
    "gsa-elibrary-scraper": (
        "библиотека/каталог GSA.",
        "не соцсети.",
    ),
    "Rebecca-Minkoff-Scraper": (
        "каталог бренда Rebecca Minkoff.",
        "не Amazon generic, не отзывы G2.",
    ),
    "GeminiBusiness_CookieExtractor": (
        "забрать cookies сессии Gemini Business (ближе к краже сессии, чем к витрине).",
        "не обычный парсер цен; не описываю как пользоваться.",
    ),
    "linkedin-jobs-scraper-incredibly-fast": (
        "вакансии LinkedIn (ещё один).",
        "не Sales Navigator.",
    ),
    "Telegram-Gift-Parser": (
        "подарки Telegram.",
        "не парсер каналов/участников; не Telegram-рассылка.",
    ),
    "cna-oab-attorney-data-scraper": (
        "справочник адвокатов (CNA/OAB).",
        "не LinkedIn.",
    ),
    "youtube-email-scraper": (
        "почты из описаний/каналов YouTube.",
        "не качалка видео; не массовая отправка писем (mailer в другой коробке).",
    ),
    "blockchain-data-crawler": (
        "транзакции/данные блокчейна.",
        "не веб-магазин.",
    ),
    "facebook-hashtag-scraper": (
        "посты Facebook по хештегу.",
        "не события и не фолловеры (это другие репы).",
    ),
    "amazon-reviews-scraper-with-advanced-filters": (
        "отзывы Amazon с фильтрами.",
        "не карточки товара (amazon-scraper); не Myntra.",
    ),
    "Google-News-Scraper": (
        "заголовки Google News.",
        "не Indian Express (отдельный репо); не OSINT-комбайн.",
    ),
    "linktree-profile-listing-scraper": (
        "ссылки с визитки Linktree.",
        "не Instagram hashtag scraper.",
    ),
    "News-Data-Scrapper-for-Indian-Express-News": (
        "лента Indian Express.",
        "не Google News.",
    ),
    "attorney-directory-scraper": (
        "справочник адвокатов.",
        "не OAB-специфичный репо; не LinkedIn.",
    ),
    "on3-recruit-scraper": (
        "спортивный рекрутинг On3.",
        "не обычный магазин.",
    ),
    "linkedin-sales-navigator-scraper": (
        "контакты/люди из LinkedIn Sales Navigator.",
        "не обычные вакансии Jobs; не рассылка найденным.",
    ),
    "D4rk_Intel-OSINT-Investigative-Toolkit": (
        "OSINT-набор для расследований.",
        "не витрина магазина.",
    ),
    "cloudinsight-extractor": (
        "вытащить данные CloudInsight / облачный отчёт.",
        "не соцсеть.",
    ),
    "Scrapstyle": (
        "скрейп с неясной целью (style?).",
        "площадка по имени не видна.",
    ),
    "Scrapy-data-extraction-pipeline": (
        "пайплайн Scrapy: универсальный движок.",
        "без паука под сайт сам ничего не знает.",
    ),
    "osint-feed": (
        "лента OSINT-индикаторов.",
        "не скрейпер шопа.",
    ),
    "spa-crawler": (
        "краулер SPA (JS-сайты).",
        "не привязан к Amazon.",
    ),
    "Whatsapp-chat-voice-Bot-with-Realtime-scraping": (
        "бот WhatsApp + скрейп чата/голоса в реальном времени.",
        "не массовая рассылка WhatsApp (это другая коробка); не парсер магазина.",
    ),
    "Instagram-Hashtag-Scraper": (
        "посты Instagram по хештегу.",
        "не фолловеры Instagram (такой качалки/парсера в keep нет); не качалка Reels.",
    ),
    "lightning-image-scraper": (
        "пачка картинок с веба.",
        "не Google Images-урок (тот отдельный); не видео.",
    ),
}

DOWNLOAD_SPEC = {
    "dab-downloader": ("скачать по протоколу/источнику DAB (радио/архив по имени).", "не YouTube и не Telegram."),
    "YoutubeDownloader": ("скачать видео YouTube.", "не плейлист отдельно (есть Playlist-репо); не TikTok."),
    "telegram-auto-clone-download": ("скачать/клонировать контент из Telegram.", "не массовая рассылка в Telegram."),
    "RemoteDownloaderPHP": ("качалка файлов по URL на PHP, цель сайта не названа.", "не заточена под YouTube по имени."),
    "YouTube-Music-Download": ("скачать YouTube Music.", "не обычные ролики/плейлисты как отдельные репы."),
    "smugmug-bulk-downloader": ("пачка фото SmugMug.", "не Pixiv (тот 404), не манга."),
    "youtube-downloader": ("скачать YouTube.", "не Spotify."),
    "takeout_downloader_script": ("скачать архив Google Takeout.", "не произвольный сайт."),
    "Bulk-Image-Downloader-Free": ("пачка картинок с веба.", "не видео YouTube."),
    "mangabuddy_downloader": ("манга MangaBuddy.", "не SmugMug, не YouTube."),
    "unlimited-kodi-downloader-download-audio-video-image-easily": ("качалка медиа под Kodi (аудио/видео/картинки).", "не официальный магазин приложений; цель сайта размыта."),
    "gallery-dl-multi-instance-downloader": ("несколько процессов gallery-dl (много сайтов картинок).", "не сам gallery-dl с улицы как новый движок — обёртка."),
    "YouTube-MP3-MP4-Downloader": ("YouTube в MP3 или MP4.", "не Music-only репо; не плейлисты отдельно."),
    "Youtube-Downloadify-app": ("приложение-качалка YouTube.", "не Telegram."),
    "YouTube-Playlist-Downloader": ("плейлист YouTube целиком.", "не одно видео; не Music."),
    "telegram-media-downloader": ("медиа из Telegram.", "не клон канала (тот другой репо); не рассылка."),
    "slidesharedownloader": ("слайды SlideShare.", "не Google Takeout, не PESU."),
    "phoenix-downloader": ("качалка с именем Phoenix, сайт-цель неясна.", "непонятно, что качает."),
    "pesu-slide-download-automator": ("слайды учебного PESU.", "не SlideShare."),
    "Bulk-Image-Downloader-Update": ("ещё одна пакетная качалка картинок.", "не манга."),
    "rekordbox-spotify-downloader": ("треки/связка Rekordbox и Spotify.", "не YouTube."),
}


def repo_of(url: str) -> str:
    return urlparse(url.strip()).path.strip("/").split("/")[-1]


def owner_repo(url: str) -> str:
    p = urlparse(url.strip()).path.strip("/")
    parts = p.split("/")
    return "/".join(parts[:2]) if len(parts) >= 2 else p


def words(repo: str) -> str:
    return " ".join(w for w in repo.replace("_", "-").replace(".", "-").split("-") if w)


def skip_soft(url: str) -> bool:
    return any(k in url.lower() for k in SKIP_SOFT)


def describe_bot(repo: str) -> tuple[str, str]:
    r = repo.lower()
    if any(x in r for x in ("polymarket", "kalshi", "solana", "raydium", "pumpfun", "hyperliquid", "mev", "arbitrage", "copy-trad", "copytrad", "trading", "trade-bot", "memecoin", "fourmeme", "four-meme", "bnb", "dex-", "sniper", "volume-bot", "market-maker", "airdrop", "kucoin", "bitpay")):
        return (
            "торговый/крипто-бот: по имени сам ставит сделки, копирует, арбитраж или накрутка объёма.",
            "не чат-бот поддержки; не рассылка VK; код биржи не проверяли — часто учебный/пустой/рискованный.",
        )
    if "chatbot" in r or "rag-chat" in r or r.endswith("-chatbot") or "ai-chatbot" in r:
        return (
            "чат-бот: отвечает на вопросы (RAG/LLM/FAQ).",
            "не ставит сделки; не массовая рассылка.",
        )
    if any(x in r for x in ("telegram", "whatsapp", "discord", "weixin", "zalo", "userbot", "tele-bot")):
        return (
            "бот в мессенджере (Telegram/WhatsApp/Discord/WeChat/Zalo) по имени.",
            "не массовая рассылка всем подряд (mailer в другой коробке); не торговля, если в имени нет биржи.",
        )
    if any(x in r for x in ("like-bot", "easyapply", "bluesky-social", "quora-trending")):
        return (
            "автодействия в соцсети: лайки, отклики, посты по имени.",
            "не парсер фолловеров; не качалка; антидетект в имени не значит, что он работает.",
        )
    if "ffmpeg" in r:
        return ("бот, который крутит ffmpeg (видео).", "не видеоредактор Vegas; не качалка YouTube.")
    if any(x in r for x in ("music-bot", "spotify-playlist", "expense", "outlook", "email-automation")):
        return ("бытовой бот: музыка, почта, расходы.", "не крипто-торговля; не рассылка по базе.")
    if "linkedin-bot" in r:
        return ("бот LinkedIn по имени (автодействия).", "не скрейпер вакансий из коробки парсеров.")
    if "dm-gateway" in r:
        return ("шлюз личных сообщений, не массовая рассылка.", "не mailer VK/WhatsApp.")
    return (
        f"бот «{words(repo)}»: крутится сам, цель узкая или только из имени.",
        "не факт, что это мессенджер или биржа; код не запускали.",
    )


def describe_skill(repo: str) -> tuple[str, str]:
    r = repo.lower()
    if "mcp" in r:
        can = f"MCP-сервер/клиент «{words(repo)}»: модель подключается к сервису/БД/инструменту из имени."
        cannot = "не скил «нарисуй лендинг», если в имени нет design/frontend; не mailer; не парсер чужого сайта, если не spider/scrape."
        if "blender" in r:
            cannot = "умение/мост к Blender, не монтаж Vegas и не качалка видео."
        if "gmail" in r or "email-design" in r:
            cannot = "доступ к почте/вёрстке писем как к MCP, не массовая рассылка."
        if "whatsapp" in r:
            cannot = "коннектор WhatsApp к модели, не WHATSENDER/рассылка."
        if "telegram" in r:
            cannot = "MCP к Telegram, не Telegram-масс-DM."
        if "datadog" in r or "jenkins" in r or "docker" in r:
            cannot = "ops/мониторинг для агента, не соцсети."
        return can, cannot
    if "openclaw" in r or "oh-my-openclaw" in r:
        return (
            "сборка/скилы OpenClaw (клиент агента) по имени.",
            "не официальный Claude; не парсер магазина.",
        )
    if any(x in r for x in ("awesome-", "skills")) and r in ("skills", "agent-skills", "awesome-claude-skills", "awesome-frontend-skills", "awesome-openclaw", "awesome-ai-agent-skills", "awesome-copilot-cowork-skills", "awesome-claude-design", "awesome-skills"):
        return (
            "каталог/подборка скилов, не одно умение.",
            "сам по себе ничего не парсит и не шлёт; это список ссылок/рецептов.",
        )
    if any(x in r for x in ("frontend", "design", "figma", "threejs", "remotion", "blender", "webdev", "unity", "ue5")):
        return (
            f"скил под задачу «{words(repo)}» (сайт/дизайн/3D/игра/видео в редакторе).",
            "не качалка с TikTok; не кряк Adobe/Vegas.",
        )
    if any(x in r for x in ("scrape", "spider", "crawl")):
        return (
            "скил/скрипт скрейпа в коробке скилов.",
            "не отдельная качалка; цель сайта смотри в имени.",
        )
    if any(x in r for x in ("ads", "seo", "affiliate", "gtm", "google-ads")):
        return (
            "скил про рекламу/SEO/аналитику по имени.",
            "не замена рекламы в чужих роликах VK; не mailer.",
        )
    if any(x in r for x in ("memory", "mem-", "recall", "session")):
        return (
            "память/сессии агента Claude/Cursor.",
            "не парсер и не бот мессенджера.",
        )
    if "claude" in r or "skill" in r:
        return (
            f"надстройка для Claude/агента: «{words(repo)}».",
            "работает только если это настоящий skill/MCP в репо, а не пустая приманка; не закрывает чужие клетки (VK-рассылка, IG-качалка), если их нет в имени.",
        )
    return (
        f"скил/MCP «{words(repo)}».",
        "цель только из имени; код не запускали.",
    )


def describe_soft_ok(repo: str) -> tuple[str, str]:
    r = repo.lower()
    if "plugin" in r or "toolkit" in r:
        return (
            f"плагин или набор утилит «{words(repo)}» к чужой среде (IDE, CMS, плеер, Open WebUI и т.п.).",
            "не самостоятельный парсер сайта и не mailer, если это не написано в имени.",
        )
    if "miner" in r and "paper" not in r:
        return ("майнер по имени (Eth-Miner).", "не плагин сайта; не описываю как майнить.")
    if "installer" in r:
        return (f"установщик «{words(repo)}».", "не кряк; не факт, что ставит заявленную программу, а не мусор.")
    if "spoofsip" in r:
        return ("по имени подмена SIP.", "не расписываю обход; для минус-списка страница GitHub открывалась.")
    return (f"софт «{words(repo)}» по имени.", "не проверяли запуск.")


def block(title: str, url: str, can: str, cannot: str) -> list[str]:
    repo = repo_of(url)
    return [
        f"### {repo}",
        url,
        f"**По имени может:** {can}",
        f"**Не умеет / не проверяли:** {cannot} Запуск кода не делали — внутри может быть пустышка или подмена.",
        "",
    ]


def load(name: str) -> list[str]:
    return [u.strip() for u in (ROOT / name).read_text().splitlines() if u.strip()]


def main() -> None:
    out: list[str] = [PREAMBLE]

    out.append("## Instagram, TikTok, SoundCloud, прокси, видео\n")
    out.extend(block(
        "", "https://github.com/kushal0451/instagram-analytics-software",
        "цифры/отчёты по Instagram (аналитика аккаунта).",
        "не парсер фолловеров, не качалка Reels/Stories, не рассылка в Direct.",
    ))
    for u, can, no in [
        ("https://github.com/Diminishing-scree890/tiktok-live-python", "читать live TikTok из Python.", "не качалка роликов TikTok; не рассылка в личку TikTok."),
        ("https://github.com/Lorenzaformic944/tiktok-live-api", "live API TikTok.", "не downloader; не постинг."),
        ("https://github.com/sotho-genuspseudobombax504/tiktok-live-nuxt", "live TikTok во фронте Nuxt.", "не качалка; не mailer."),
        ("https://github.com/Ninju153311/soundcloud-api-ts-next", "официальная/обёрточная API SoundCloud в TS/Next.", "не качалка треков в обход; не парсер чужих плейлистов как bulk downloader."),
        ("https://github.com/Lokmandev/codenex-ai-api-proxy", "прокладка к AI API.", "не HTTP-прокси для парсера сайтов; не IPv6-пул."),
        ("https://github.com/despiteportablecomputer411/proxy-ipv6-generator", "генерировать IPv6-адреса/прокси.", "не коннектор к Claude; не обход Cloudflare сам по себе."),
        ("https://github.com/kazhuki7/agentskills-proxy", "прокси для agent skills (ещё в скилах).", "не парсер; не mailer."),
        ("https://github.com/Indraparama940/ai-ffmpeg-cli", "командная строка ffmpeg + ИИ.", "не GUI-редактор; не кряк Vegas; не качалка с сайта."),
        ("https://github.com/NileshKavindaNaka/ffmpeg-video-bot", "бот, который вызывает ffmpeg.", "не монтаж как Premiere; не качалка YouTube."),
        ("https://github.com/hussabd/vue-video-editor", "монтаж в браузере на Vue.", "не ffmpeg-CLI; не пиратский Vegas."),
    ]:
        out.extend(block("", u, can, no))
    out.append("Vegas Pro в `видео.txt` — запись из кряков, возможности не расписываю. Файл: `и-видео-и-кряк.txt`.\n")

    out.append("## Парсеры\n")
    for u in load("парсер.txt"):
        repo = repo_of(u)
        if repo in PARSER_SPEC:
            can, no = PARSER_SPEC[repo]
        else:
            can, no = (
                f"сбор данных «{words(repo)}» с чужого сайта/API по имени.",
                "только то, что в имени; не другие площадки.",
            )
        out.extend(block("", u, can, no))

    out.append("## Качалки\n")
    for u in load("качалка.txt"):
        repo = repo_of(u)
        can, no = DOWNLOAD_SPEC.get(
            repo,
            (f"скачать файлы «{words(repo)}».", "не другие сайты из имени."),
        )
        out.extend(block("", u, can, no))

    out.append("## Боты\n")
    for u in load("бот.txt"):
        can, no = describe_bot(repo_of(u))
        out.extend(block("", u, can, no))

    out.append("## Скилы и MCP\n")
    for u in load("скил_mcp.txt"):
        can, no = describe_skill(repo_of(u))
        out.extend(block("", u, can, no))

    out.append("## Софт (нейтральные имена)\n")
    skipped = 0
    for u in load("софт.txt"):
        if skip_soft(u):
            skipped += 1
            continue
        can, no = describe_soft_ok(repo_of(u))
        out.extend(block("", u, can, no))
    out.append(
        f"В `софт.txt` ещё **{skipped}** записей с именами RAT / inject / bypass / brute / checker / payload. "
        "Возможности не расписываю. Сырой список: `софт.txt`.\n"
    )

    out.append("## Не расписываю по возможностям\n")
    out.append("- кряки / no-trial: `кряк_чит.txt` (38 URL, страница GitHub открывалась).")
    out.append("- стилеры: `стилер.txt`")
    out.append("- рассылки: `рассылка.txt`")
    out.append("- авторегер/токены: `авторегер.txt`")
    out.append("")

    path = ROOT / "НАЙДЕНО.md"
    path.write_text("\n".join(out), encoding="utf-8")
    print("wrote", path, "lines", len(out), "bytes", path.stat().st_size)


if __name__ == "__main__":
    main()
