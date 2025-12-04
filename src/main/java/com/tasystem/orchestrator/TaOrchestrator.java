package com.tasystem.orchestrator;

import com.tasystem.common.TaEnums.FileType;
import com.tasystem.common.TaEnums.SystemPhase;
import com.tasystem.common.TaEnums.TaskStatus;
import com.tasystem.model.MonitorTask;
// 引用拆分后的处理器类
import com.tasystem.processor.NavProcessor;
import com.tasystem.processor.AccountProcessor;
import com.tasystem.processor.TradeProcessor;
import com.tasystem.processor.ConfirmProcessor;
import com.tasystem.repository.MonitorRepository;
import com.tasystem.repository.TaDataRepository;
import lombok.extern.slf4j.Slf4j;

import java.io.File;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.stream.Collectors;

@Slf4j
public class TaOrchestrator {

    private final MonitorRepository monitorRepo = MonitorRepository.getInstance();
    private final TaDataRepository dataRepo = TaDataRepository.getInstance();
    
    private final ExecutorService executor = Executors.newFixedThreadPool(5);
    private final String ROOT_DIR = System.getenv().getOrDefault("TA_ROOT_DIR", "/app/data");

    private SystemPhase currentPhase = SystemPhase.BATCH_1_APPLY;

    // 实例化拆分后的处理器
    private final NavProcessor navProcessor = new NavProcessor();
    private final AccountProcessor accProcessor = new AccountProcessor();
    private final TradeProcessor tradeProcessor = new TradeProcessor();
    private final ConfirmProcessor confirmProcessor = new ConfirmProcessor();

    public void start() {
        log.info(">>> TA 编排器启动...");
        
        // 1. 加载存量业务数据
        dataRepo.loadData();
        
        // 2. 初始化排程
        monitorRepo.initDailySchedule();

        // 3. 启动主循环
        new Thread(this::orchestrateLoop, "Orchestrator-Thread").start();
    }

    private void orchestrateLoop() {
        while (true) {
            try {
                List<MonitorTask> currentPhaseTasks = getTasksByPhase(currentPhase);
                
                processPhaseTasks(currentPhaseTasks);

                if (currentPhase == SystemPhase.BATCH_1_APPLY) {
                    checkAndSwitchPhase(currentPhaseTasks);
                } 
                else if (currentPhase == SystemPhase.BATCH_2_CONFIRM) {
                    checkAndShutdown(currentPhaseTasks);
                }

                Thread.sleep(1000); 

            } catch (Exception e) {
                log.error("编排循环异常", e);
                try { Thread.sleep(5000); } catch (InterruptedException ex) {}
            }
        }
    }

    private void checkAndShutdown(List<MonitorTask> phase2Tasks) {
        boolean allFinished = true;
        for (MonitorTask task : phase2Tasks) {
            if (!isTaskFinished(task)) {
                allFinished = false;
                break;
            }
        }

        if (allFinished) {
            log.info("##########################################################");
            log.info("### 任务清零。正在执行数据落盘并退出...                 ###");
            log.info("##########################################################");
            
            dataRepo.dumpData();
            executor.shutdown();
            System.exit(0);
        }
    }

    private List<MonitorTask> getTasksByPhase(SystemPhase phase) {
        List<MonitorTask> allTasks = new ArrayList<>();
        allTasks.addAll(monitorRepo.getManagerTaskTable());
        allTasks.addAll(monitorRepo.getDistributorTaskTable());

        if (phase == SystemPhase.BATCH_1_APPLY) {
            return allTasks.stream()
                    .filter(t -> t.getFileType() != FileType.MGR_CONFIRM)
                    .collect(Collectors.toList());
        } else {
            return allTasks.stream()
                    .filter(t -> t.getFileType() == FileType.MGR_CONFIRM)
                    .collect(Collectors.toList());
        }
    }

    private void processPhaseTasks(List<MonitorTask> tasks) {
        for (MonitorTask task : tasks) {
            if (isTaskFinished(task) || task.getStatus() == TaskStatus.PROCESSING) {
                continue;
            }
            if (task.getStatus() == TaskStatus.WAITING_FILE) {
                checkFileArrival(task);
            }
            if (task.getStatus() == TaskStatus.FILE_RECEIVED) {
                if (canProcess(task)) {
                    task.setStatus(TaskStatus.READY_TO_PROCESS);
                }
            }
            if (task.getStatus() == TaskStatus.READY_TO_PROCESS) {
                submitTask(task);
            }
        }
    }

    private void checkAndSwitchPhase(List<MonitorTask> phase1Tasks) {
        boolean allFinished = true;
        for (MonitorTask task : phase1Tasks) {
            if (!isTaskFinished(task)) {
                allFinished = false;
                break;
            }
        }
        if (allFinished) {
            log.info("### 切换至 确认批次(Batch 2) ###");
            currentPhase = SystemPhase.BATCH_2_CONFIRM;
        }
    }

    private boolean isTaskFinished(MonitorTask task) {
        return task.getStatus() == TaskStatus.PROCESSED || 
               task.getStatus() == TaskStatus.FAILED;
    }

    private void checkFileArrival(MonitorTask task) {
        String subDir = (task.getFileType() == FileType.MGR_NAV || task.getFileType() == FileType.MGR_CONFIRM) 
                        ? "inbox/manager" : "inbox/distributor";
        File f = new File(ROOT_DIR + "/" + subDir, task.getExpectedFileName());
        
        if (f.exists()) {
            log.info("[Event] 物理文件已到达: {}", task.getExpectedFileName());
            task.setFullPath(f.getAbsolutePath());
            task.setStatus(TaskStatus.FILE_RECEIVED);
        }
    }

    private boolean canProcess(MonitorTask task) {
        if (task.getDependencyTaskId() != null) {
            MonitorTask parent = monitorRepo.findTaskById(task.getDependencyTaskId());
            if (parent == null || parent.getStatus() != TaskStatus.PROCESSED) return false; 
        }
        if (task.getFileType() == FileType.DIST_TRADE) {
            String fundCode = task.getRelatedFundCode();
            if (fundCode != null && !monitorRepo.getNavTable().containsKey(fundCode)) return false; 
        }
        return true;
    }

    private void submitTask(MonitorTask task) {
        log.info("[Action] 提交处理: {}", task.getTaskId());
        task.setStatus(TaskStatus.PROCESSING);
        executor.submit(() -> {
            switch (task.getFileType()) {
                case MGR_NAV -> navProcessor.execute(task);
                case MGR_CONFIRM -> confirmProcessor.execute(task);
                case DIST_ACC -> accProcessor.execute(task);
                case DIST_TRADE -> tradeProcessor.execute(task);
            }
        });
    }
}