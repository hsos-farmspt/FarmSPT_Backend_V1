# Set mosquitto and plugin version
ARG MOSQUITTO_VERSION=2.0.18
ARG OAUTH_PLUGIN_VERSION=1.0.0

# Configuration defaults
#ARG MOSQUITTO_PORT=1883
ARG OAUTH_JWT_KEY=MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEArm1DSPyGbHkQXMz1QYFBAMwglUB5PH+L+OlTMXSiSB43yQsf/7T6QLwqIuLYaTsH+5qh1mur6KI4XGgjjq3sAYj5POLPkc/9BjyzdMqWurY22wXRikZuENkDlxkuapRfiUmG3qcwWEZlk+3tdYRNlziuzhnlLGPajbH0mwRUHVzskATbtTqbdmeafvqDOVduxQLgzK0xAfgpTC45IAD/HAaYP2s9vxJA+3RaSUnACVTW9k/OEOhb7FaR1tlc7xPw4ZnPhAA4p8zrzmNbhPlrmUXiemFDyTCZXr2TMztPpBoTrmDvM4kaOsgTePBJFkSnvLIJQBEALaAzLrhYDYtLywIDAQAB
ARG OAUTH_JWT_VALIDATE_EXP=false
ARG OAUTH_CLIENT_ID=mqtt-api
ARG OAUTH_CLIENT_SECRET=xShUl56DbPaMtXb8JMLzH2HIfEDh0fiz
ARG OAUTH_TOKEN_URL=https://keycloak.farmspt.ai.edvsz.hs-osnabrueck.de/realms/FarmSPT_extension_mqtt/protocol/openid-connect/token


FROM alpine:3.20
ARG MOSQUITTO_VERSION
ARG OAUTH_PLUGIN_VERSION
#ARG MOSQUITTO_PORT
ARG OAUTH_JWT_KEY
ARG OAUTH_JWT_VALIDATE_EXP
ARG OAUTH_CLIENT_ID
ARG OAUTH_CLIENT_SECRET
ARG OAUTH_TOKEN_URL

# Install necessary build dependencies
RUN apk update && apk add --no-cache --virtual build-deps \
    build-base \
    cmake \
    openssl-dev \
    cjson-dev \
    libwebsockets-dev \
    curl-dev \
    jansson-dev \
    libjwt-dev

# Build mosquitto from source
RUN wget http://mosquitto.org/files/source/mosquitto-${MOSQUITTO_VERSION}.tar.gz
RUN tar xzvf mosquitto-${MOSQUITTO_VERSION}.tar.gz
RUN cd mosquitto-${MOSQUITTO_VERSION} \
    && make WITH_WEBSOCKETS=yes WITH_ADNS=no WITH_DOCS=no WITH_SRV=no prefix=/usr \
    && make install \
    && cd .. \
    && rm -rf mosquitto-${MOSQUITTO_VERSION} mosquitto-${MOSQUITTO_VERSION}.tar.gz 

# Build the mosquitto-oauth-plugin from source
RUN wget https://github.com/iotinga/mosquitto-oauth-plugin/archive/refs/tags/v${OAUTH_PLUGIN_VERSION}.tar.gz -O mosquitto-oauth-plugin-${OAUTH_PLUGIN_VERSION}.tar.gz
RUN tar xzvf mosquitto-oauth-plugin-${OAUTH_PLUGIN_VERSION}.tar.gz
RUN cd mosquitto-oauth-plugin-${OAUTH_PLUGIN_VERSION} \
    && mkdir build && cd build \
    && cmake .. \
    && make \
    && make install \
    && cd .. \
    && rm -rf mosquitto-oauth-plugin-${OAUTH_PLUGIN_VERSION} mosquitto-oauth-plugin-${OAUTH_PLUGIN_VERSION}.tar.gz

# Remove build dependencies
RUN apk del build-deps

# Install runtime dependencies
RUN apk add --no-cache \
    ca-certificates \
    openssl \
    cjson \
    libressl \
    libwebsockets \
    curl \
    jansson \
    libjwt 

# Create mosquitto directories
RUN mkdir -p /mosquitto/config /mosquitto/data /mosquitto/log

# Create mosquitto system user
RUN addgroup -S mosquitto \
    && adduser -S -D -H -s /sbin/nologin -G mosquitto -g mosquitto mosquitto \
    && chown -R mosquitto:mosquitto /mosquitto

# Add default configuration
COPY FarmSPT_MQTT/mosquitto-example.conf /mosquitto/config/mosquitto.conf

# Write mosquitto configuration directly
#RUN cat > /mosquitto/config/mosquitto.conf << 'EOF'
#listener 1883 0.0.0.0

#plugin /usr/local/lib/mosquitto-oauth-plugin.so

#plugin_opt_oauth_jwt_key ${OAUTH_JWT_KEY}
#plugin_opt_oauth_jwt_validate_exp ${OAUTH_JWT_VALIDATE_EXP}

#plugin_opt_oauth_client_id ${OAUTH_CLIENT_ID}
#plugin_opt_oauth_client_secret ${OAUTH_CLIENT_SECRET}
#plugin_opt_oauth_token_url ${OAUTH_TOKEN_URL}

#log_dest file /mosquitto/log/mosquitto.log
#log_type all
#EOF

# Set proper permissions for mosquitto config
#RUN chown mosquitto:mosquitto /mosquitto/config/mosquitto.conf \
   # && chmod 644 /mosquitto/config/mosquitto.conf

# Set up entry point
VOLUME ["/mosquitto/data", "/mosquitto/log"]
EXPOSE 1883
CMD ["/usr/local/sbin/mosquitto", "-c", "/mosquitto/config/mosquitto.conf"]