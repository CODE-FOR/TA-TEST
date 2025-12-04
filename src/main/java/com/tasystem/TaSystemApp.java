package com.tasystem;

import com.tasystem.orchestrator.TaOrchestrator;
import lombok.extern.slf4j.Slf4j;

/**
 * 应用程序启动入口
 */
@Slf4j
public class TaSystemApp {
    public static void main(String[] args) {
        log.info("==========================================");
        log.info("   TA 仿真系统 (Schedule-Driven Mode) 09:52");
        log.info("==========================================");

        TaOrchestrator orchestrator = new TaOrchestrator();
        orchestrator.start();
        
        // 阻塞主线程，保持容器运行
        try {
            Thread.currentThread().join();
        } catch (InterruptedException e) {
            e.printStackTrace();
        }
    }
}