# Образ Node.js 20 для фронтенда
FROM node:20-alpine
WORKDIR /app
# Копируем и устанавливаем зависимости
COPY package*.json ./
RUN npm install
# Копируем код приложения
COPY . .
EXPOSE 5173
# Запускаем Vite dev сервер
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
