FROM nginx:1.21.0-alpine

RUN apk add --update npm git
RUN npm install -g npm@8.1.3
COPY ./default.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
WORKDIR /frontend

CMD ["nginx", "-g", "daemon off;"]
