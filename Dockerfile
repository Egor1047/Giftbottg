FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
VOLUME /app/data
CMD sh -c "python -m http.server $PORT & python finder.py & exec python bot.py"
