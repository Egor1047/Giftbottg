FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
CMD sh -c "python -m http.server $PORT & python bot.py"
