#!/usr/bin/env bash
# Regraba capturas, GIFs y vídeo con Gemma. Uso (desde la carpeta del proyecto, con el entorno activado):
#   ollama serve   # si no está ya en marcha (brew services start ollama)
#   bash docs/grabar.sh
# Pone datos de ejemplo (guarda antes una copia de los tuyos), arranca el servidor solo y lo para al acabar.
set -euo pipefail
cd "$(dirname "$0")/.."
PORT=8765
pip install -q playwright && python -m playwright install chromium
curl -fsS http://localhost:11434/api/tags >/dev/null || { echo "Ollama no responde: ejecuta 'brew services start ollama'"; exit 1; }
python manage.py migrate -v0
python manage.py demo --reset --yes
PASS="grab-$RANDOM-$RANDOM"
python manage.py shell -c "
from django.contrib.auth import get_user_model as g
U=g(); u,_=U.objects.get_or_create(username='grabador', defaults={'is_staff':True,'is_superuser':True}); u.set_password('$PASS'); u.save()"
python manage.py runserver $PORT --noreload >/tmp/taller-grabar.log 2>&1 &
SRV=$!
trap 'kill $SRV 2>/dev/null; python manage.py shell -c "from django.contrib.auth import get_user_model as g; g().objects.filter(username=\"grabador\").delete()"' EXIT
sleep 4
TALLER_BASE=http://127.0.0.1:$PORT TALLER_USER=grabador TALLER_PASS=$PASS python docs/record_demo.py
echo "Listo: docs/media/"
