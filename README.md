# Yandex AmbiSync

Синхронизация цвета [умной эмби-лампы Яндекса](https://alice.yandex.ru/smart-home/smart-lamp) со средним цветом экрана Windows.

![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)

## Возможности

- Захват среднего цвета выбранного монитора
- Плавное сглаживание переходов
- Управление через **Yandex Smart Home API**
- Работа **в системном трее** и в фоне
- Сборка в **portable .exe** без установки Python

## Скачать

Готовый `YandexAmbiSync.exe` в [Releases](https://github.com/botukcs/ambiwin/releases)

Или:

```powershell
.\scripts\build.ps1
```

## Быстрый старт (из исходников)

```powershell
git clone https://github.com/botukcs/ambiwin/yandex-ambisync.git
cd yandex-ambisync
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

## Настройка лампы

### 1. OAuth-приложение

1. [oauth.yandex.ru/client/new](https://oauth.yandex.ru/client/new) → «Для доступа к API»
2. Доступы: `iot:view`, `iot:control`
3. Redirect URI: `https://oauth.yandex.ru/verification_code`

### 2. Токен и лампа

1. Получите токен через кнопку «Открыть страницу авторизации»
2. Скопируйте код со страницы `verification_code` в поле OAuth
3. **Загрузить** → выберите эмби-лампу → **Сохранить** → **Старт**

Конфиг: `%USERPROFILE%\.config\yandex-ambisync\config.json`

## Системный трей

Закрытие окна (✕) **сворачивает в трей** - синхронизация продолжается

| Опция | Описание |
|-------|----------|
| Сворачивать в трей | При ✕ не выходить, а скрывать окно |
| Запускать свёрнутым | Старт сразу в трей |

## Рекомендуемые настройки (плавный режим)

| Параметр | Значение |
|----------|----------|
| FPS | 10 |
| Сглаживание | 0.22 |
| Порог для лампы | 4 |
| Downsample | 18 |

Кнопка **«Плавный режим»** в настройках выставляет их автоматически.
