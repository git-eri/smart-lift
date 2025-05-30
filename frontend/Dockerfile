# build stage
FROM node:24.1-slim AS build-stage
ARG VITE_USE_SSL=false
ARG VITE_BACKEND_PORT=8000
ENV VITE_USE_SSL=$VITE_USE_SSL
ENV VITE_BACKEND_PORT=$VITE_BACKEND_PORT
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

# production stage
FROM nginx:stable-alpine AS production-stage
ARG USE_SELF_SIGNED_CERT=false
ENV USE_SELF_SIGNED_CERT=$USE_SELF_SIGNED_CERT
COPY --from=build-stage /app/dist /usr/share/nginx/html
COPY nginx.template.conf /etc/nginx/templates/nginx.template.conf
COPY start.sh /start.sh
RUN chmod +x /start.sh
EXPOSE 80 443
CMD ["/start.sh"]