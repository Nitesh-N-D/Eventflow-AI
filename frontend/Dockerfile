FROM node:20-slim AS builder

WORKDIR /app

COPY frontend/package.json /app/package.json
RUN npm install

COPY frontend/ /app/

ARG VITE_API_URL=https://eventflow-ai-backend.onrender.com
ENV VITE_API_URL=$VITE_API_URL

RUN npm run build

FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
