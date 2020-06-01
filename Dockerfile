FROM python:3.7
RUN mkdir /app
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
CMD ["/app/run.sh"]