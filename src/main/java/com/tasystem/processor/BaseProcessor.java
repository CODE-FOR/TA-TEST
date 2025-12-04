package com.tasystem.processor;

import com.tasystem.common.TaEnums.TaskStatus;
import com.tasystem.model.MonitorTask;
import lombok.extern.slf4j.Slf4j;

import java.io.File;

/**
 * 处理器基类
 * 负责通用的文件存在性检查、目录创建、异常捕获和状态更新。
 */
@Slf4j
public abstract class BaseProcessor {

    protected static final String OUTBOX_MGR = "/app/data/outbox/manager";
    protected static final String OUTBOX_DIST = "/app/data/outbox/distributor";

    public void execute(MonitorTask task) {
        log.info(">> [Processor] 开始处理任务: {}", task.getTaskId());
        try {
            // 确保输出目录存在
            new File(OUTBOX_MGR).mkdirs();
            new File(OUTBOX_DIST).mkdirs();

            File f = new File(task.getFullPath());
            if (!f.exists() || f.length() == 0) {
                log.warn("   文件不存在或为空: {}", task.getExpectedFileName());
            } else {
                processLogic(task);
            }
            
            task.setStatus(TaskStatus.PROCESSED);
            task.setMessage("Success");
            log.info("<< [Processor] 任务完成: {}", task.getTaskId());
            
        } catch (Exception e) {
            log.error("XX [Processor] 任务失败: " + task.getTaskId(), e);
            task.setStatus(TaskStatus.FAILED);
            task.setMessage(e.getMessage());
        }
    }

    /**
     * 具体业务逻辑，由子类实现
     */
    protected abstract void processLogic(MonitorTask task) throws Exception;
}