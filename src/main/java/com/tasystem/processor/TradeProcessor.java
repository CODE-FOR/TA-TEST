package com.tasystem.processor;

import com.tasystem.model.Account;
import com.tasystem.model.Holding;
import com.tasystem.model.MonitorTask;
import com.tasystem.model.Transaction;
import com.tasystem.repository.MonitorRepository;
import com.tasystem.repository.TaDataRepository;
import lombok.extern.slf4j.Slf4j;
import org.apache.commons.csv.CSVFormat;
import org.apache.commons.csv.CSVParser;
import org.apache.commons.csv.CSVPrinter;
import org.apache.commons.csv.CSVRecord;

import java.io.File;
import java.io.FileReader;
import java.io.FileWriter;
import java.io.Reader;
import java.math.BigDecimal;
import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;

@Slf4j
public class TradeProcessor extends BaseProcessor {

    @Override
    protected void processLogic(MonitorTask task) throws Exception {
        MonitorRepository monitorRepo = MonitorRepository.getInstance();
        TaDataRepository dataRepo = TaDataRepository.getInstance();
        List<Transaction> validTransactions = new ArrayList<>(); // 校验通过的交易

        log.info("   -> [交易] 开始处理看穿式交易申请...");

        CSVFormat readFormat = CSVFormat.DEFAULT.builder()
                .setHeader()
                .setSkipHeaderRecord(true)
                .build();

        try (Reader reader = new FileReader(task.getFullPath());
             CSVParser parser = new CSVParser(reader, readFormat)) {

            for (CSVRecord r : parser) {
                String transId = r.get("trans_id");
                String fundCode = r.get("fund_code");
                String type = r.get("type"); // PURCHASE or REDEEM
                BigDecimal value = new BigDecimal(r.get("amount_or_shares"));
                String accountId = r.get("account_id");

                Transaction tx = Transaction.builder()
                        .transId(transId)
                        .fundCode(fundCode)
                        .accountId(accountId)
                        .distributorId(task.getSenderId())
                        .type(type)
                        .status("APPLIED")
                        .build();

                // --- 核心看穿式校验逻辑 ---
                boolean checkPassed = true;
                String failReason = "";

                // 1. 验账户
                Account account = dataRepo.getAccountMap().get(accountId);
                if (account == null) {
                    checkPassed = false;
                    failReason = "ACCOUNT_NOT_FOUND";
                } else if (!"NORMAL".equals(account.getStatus())) {
                    checkPassed = false;
                    failReason = "ACCOUNT_STATUS_ABNORMAL";
                }

                // 2. 验持仓 (仅限赎回)
                if (checkPassed && "REDEEM".equals(type)) {
                    String holdKey = Holding.generateKey(accountId, fundCode);
                    Holding holding = dataRepo.getHoldingMap().get(holdKey);
                    
                    // 检查是否有持仓记录，以及份额是否充足
                    if (holding == null || holding.getAvailableShares().compareTo(value) < 0) {
                        checkPassed = false;
                        failReason = "INSUFFICIENT_SHARES";
                        log.warn("      [拒单] 赎回份额不足: Acc={}, Need={}, Has={}",
                                accountId, value, (holding == null ? 0 : holding.getAvailableShares()));
                    } else {
                        tx.setShares(value); // 赎回按份额
                    }
                } else if (checkPassed && "PURCHASE".equals(type)) {
                    tx.setAmount(value); // 申购按金额
                }

                if (checkPassed) {
                    tx.setStatus("REPORTED_TO_MGR");
                    validTransactions.add(tx);
                    monitorRepo.getTransactionTable().put(transId, tx);
                    log.info("      [受理] 交易通过校验: ID={}, Type={}, Val={}", transId, type, value);
                } else {
                    tx.setStatus("TA_REJECTED");
                    tx.setMessage(failReason);
                    monitorRepo.getTransactionTable().put(transId, tx);
                    log.warn("      [拒单] ID={}, 原因={}", transId, failReason);
                }
            }
        }

        // --- 生成发给管理人的文件 (TO_MGR_APPLY) ---
        if (!validTransactions.isEmpty()) {
            String dateStr = LocalDate.now().format(DateTimeFormatter.ofPattern("yyyyMMdd"));
            // 假设同一批次只有一个基金，或简单取第一个基金代码命名
            String outFileName = String.format("TO_MGR_APPLY_%s_%s.csv",
                    validTransactions.get(0).getFundCode(), dateStr);
            File outFile = new File(OUTBOX_MGR, outFileName);

            CSVFormat writeFormat = CSVFormat.DEFAULT.builder()
                    .setHeader("trans_id", "fund_code", "type", "amount", "shares", "apply_time")
                    .build();

            try (FileWriter fw = new FileWriter(outFile);
                 CSVPrinter p = new CSVPrinter(fw, writeFormat)) {
                
                for (Transaction tx : validTransactions) {
                    p.printRecord(
                            tx.getTransId(),
                            tx.getFundCode(),
                            tx.getType(),
                            tx.getAmount(),
                            tx.getShares(),
                            LocalDateTime.now()
                    );
                }
            }
            log.info("   -> [生成] 发往管理人文件: {}", outFile.getAbsolutePath());
        }
    }
}