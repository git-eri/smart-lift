# build stage
FROM node:24.11-slim AS build
WORKDIR /code
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

# production stage
FROM nginx:mainline-alpine
COPY --from=build /code/dist /usr/share/nginx/html
#COPY nginx.template.conf /etc/nginx/templates/nginx.template.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
