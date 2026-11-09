FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
CMD sh -c "python -m http.server 10000 & python bot.py"
