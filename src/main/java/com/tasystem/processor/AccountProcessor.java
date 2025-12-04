package com.tasystem.processor;

import com.tasystem.model.Account;
import com.tasystem.model.MonitorTask;
import com.tasystem.repository.TaDataRepository;
import lombok.AllArgsConstructor;
import lombok.Data;
import lombok.extern.slf4j.Slf4j;
import org.apache.commons.csv.CSVFormat;
import org.apache.commons.csv.CSVParser;
import org.apache.commons.csv.CSVPrinter;
import org.apache.commons.csv.CSVRecord;

import java.io.File;
import java.io.FileReader;
import java.io.FileWriter;
import java.io.Reader;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;

@Slf4j
public class AccountProcessor extends BaseProcessor {

    @Data @AllArgsConstructor
    private static class AccountConfirmRecord {
        String requestNo;
        String bizCode;
        String accountId;
        String status;
        String message;
    }

    @Override
    protected void processLogic(MonitorTask task) throws Exception {
        TaDataRepository dataRepo = TaDataRepository.getInstance();
        log.info("   -> [账户] 开始解析账户申请...");

        List<AccountConfirmRecord> confirmList = new ArrayList<>();

        CSVFormat format = CSVFormat.DEFAULT.builder()
                .setHeader()
                .setSkipHeaderRecord(true)
                .build();

        try (Reader reader = new FileReader(task.getFullPath());
             CSVParser parser = new CSVParser(reader, format)) {

            for (CSVRecord r : parser) {
                String reqNo = r.get("request_no");
                String bizCode = r.get("biz_code");
                String name = r.get("investor_name");
                String idNo = r.get("id_no");
                String senderId = task.getSenderId();

                if ("001".equals(bizCode)) { // 开户
                    Account existing = dataRepo.findByIdNo(idNo);
                    if (existing != null) {
                        log.warn("      [开户失败] 证件号已存在: {}", idNo);
                        confirmList.add(new AccountConfirmRecord(reqNo, bizCode, existing.getAccountId(), "0", "ID_EXISTS"));
                    } else {
                        String newAccId = "TA" + Math.abs(idNo.hashCode());
                        Account acc = Account.builder()
                                .distributorId(senderId)
                                .accountId(newAccId)
                                .name(name)
                                .idNo(idNo)
                                .status("NORMAL")
                                .openTime(LocalDateTime.now())
                                .updateTime(LocalDateTime.now())
                                .build();
                        dataRepo.getAccountMap().put(newAccId, acc);
                        log.info("      [开户成功] {}, 账号: {}", name, newAccId);
                        confirmList.add(new AccountConfirmRecord(reqNo, bizCode, newAccId, "1", "SUCCESS"));
                    }

                } else if ("002".equals(bizCode)) { // 销户
                    Account acc = dataRepo.findByIdNo(idNo);
                    if (acc != null) {
                        acc.setStatus("CLOSED");
                        acc.setUpdateTime(LocalDateTime.now());
                        log.info("      [销户成功] {}, 账号: {}", name, acc.getAccountId());
                        confirmList.add(new AccountConfirmRecord(reqNo, bizCode, acc.getAccountId(), "1", "SUCCESS"));
                    } else {
                        log.warn("      [销户失败] 未找到账户: {}", idNo);
                        confirmList.add(new AccountConfirmRecord(reqNo, bizCode, "", "0", "ACCOUNT_NOT_FOUND"));
                    }
                }
            }
        }

        // --- 生成账户确认文件 ---
        if (!confirmList.isEmpty()) {
            String dateStr = LocalDate.now().format(DateTimeFormatter.ofPattern("yyyyMMdd"));
            String outFileName = String.format("TO_DIST_ACC_CONFIRM_%s.csv", dateStr);
            File outFile = new File(OUTBOX_DIST, outFileName);

            CSVFormat writeFormat = CSVFormat.DEFAULT.builder()
                    .setHeader("request_no", "biz_code", "ta_account_id", "status", "message", "confirm_time")
                    .build();

            try (FileWriter fw = new FileWriter(outFile);
                 CSVPrinter printer = new CSVPrinter(fw, writeFormat)) {

                for (AccountConfirmRecord rec : confirmList) {
                    printer.printRecord(
                            rec.getRequestNo(),
                            rec.getBizCode(),
                            rec.getAccountId(),
                            rec.getStatus(),
                            rec.getMessage(),
                            LocalDateTime.now()
                    );
                }
            }
            log.info("   -> [生成文件] 账户确认文件已生成: {}", outFile.getAbsolutePath());
        }
    }
}