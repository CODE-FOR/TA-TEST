FROM openjdk:21-ea-jdk-slim

WORKDIR /app

# 复制构建好的 jar 包到容器中
COPY target/simple-ta-agent-1.0-SNAPSHOT.jar app.jar

# 设置环境变量，指定数据根目录
ENV TA_ROOT_DIR=/app/data

# 启动应用程序
ENTRYPOINT ["java", "-jar", "app.jar"]