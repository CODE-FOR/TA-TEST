package com.tasystem.processor;

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
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;

@Slf4j
public class ConfirmProcessor extends BaseProcessor {

    @Override
    protected void processLogic(MonitorTask task) throws Exception {
        MonitorRepository monitorRepo = MonitorRepository.getInstance();
        TaDataRepository dataRepo = TaDataRepository.getInstance();
        List<Transaction> confirmedTxs = new ArrayList<>();
        List<Transaction> rejectedTxs = new ArrayList<>();

        log.info("   -> [确认] 开始处理管理人确认及份额过账...");

        CSVFormat readFormat = CSVFormat.DEFAULT.builder()
                .setHeader()
                .setSkipHeaderRecord(true)
                .build();

        try (Reader reader = new FileReader(task.getFullPath());
             CSVParser parser = new CSVParser(reader, readFormat)) {

            for (CSVRecord r : parser) {
                String transId = r.get("trans_id");
                String status = r.get("status"); // 1=成功
                BigDecimal cfmShares = new BigDecimal(r.get("confirmed_shares"));
                BigDecimal cfmNav = new BigDecimal(r.get("confirmed_nav"));

                Transaction tx = monitorRepo.getTransactionTable().get(transId);
                if (tx != null) {
                    if ("1".equals(status)) {
                        tx.setStatus("CONFIRMED");
                        tx.setShares(cfmShares);
                        tx.setNav(cfmNav);
                        confirmedTxs.add(tx);

                        // --- 份额过账 ---
                        updateHoldings(dataRepo, tx);

                    } else {
                        tx.setStatus("REJECTED");
                        tx.setMessage("REJECTED_BY_MGR");
                        rejectedTxs.add(tx);
                    }
                }
            }
        }

        // 把在交易处理阶段就被 TA_REJECTED 的交易加入回报列表
        for (Transaction tx : monitorRepo.getTransactionTable().values()) {
            if ("TA_REJECTED".equals(tx.getStatus())) {
                rejectedTxs.add(tx);
            }
        }

        // --- 生成确认回报文件 (TO_DIST_CONFIRM) ---
        List<Transaction> allReports = new ArrayList<>(confirmedTxs);
        allReports.addAll(rejectedTxs);

        if (!allReports.isEmpty()) {
            String dateStr = LocalDate.now().format(DateTimeFormatter.ofPattern("yyyyMMdd"));
            String outFileName = String.format("TO_DIST_CONFIRM_%s.csv", dateStr);
            File outFile = new File(OUTBOX_DIST, outFileName);

            CSVFormat writeFormat = CSVFormat.DEFAULT.builder()
                    .setHeader("trans_id", "fund_code", "account_id", "type", "status", "confirmed_shares", "confirmed_nav", "message")
                    .build();

            try (FileWriter fw = new FileWriter(outFile);
                 CSVPrinter p = new CSVPrinter(fw, writeFormat)) {
                
                for (Transaction tx : allReports) {
                    p.printRecord(
                            tx.getTransId(),
                            tx.getFundCode(),
                            tx.getAccountId(),
                            tx.getType(),
                            tx.getStatus(),
                            tx.getShares(),
                            tx.getNav(),
                            tx.getMessage()
                    );
                }
            }
            log.info("   -> [生成] 发往销售商确认文件: {}", outFile.getAbsolutePath());
        }
    }

    private void updateHoldings(TaDataRepository dataRepo, Transaction tx) {
        String key = Holding.generateKey(tx.getAccountId(), tx.getFundCode());
        Holding holding = dataRepo.getHoldingMap().get(key);

        if (holding == null) {
            if ("PURCHASE".equals(tx.getType())) {
                holding = Holding.builder()
                        .accountId(tx.getAccountId())
                        .fundCode(tx.getFundCode())
                        .totalShares(BigDecimal.ZERO)
                        .availableShares(BigDecimal.ZERO)
                        .build();
                dataRepo.getHoldingMap().put(key, holding);
            } else {
                log.error("严重错误：赎回确认成功但无持仓记录！TransId={}", tx.getTransId());
                return;
            }
        }

        BigDecimal delta = tx.getShares();
        if ("PURCHASE".equals(tx.getType())) {
            holding.setTotalShares(holding.getTotalShares().add(delta));
            holding.setAvailableShares(holding.getAvailableShares().add(delta));
            log.info("      [过账] 申购加仓: Acc={}, Fund={}, +{}", tx.getAccountId(), tx.getFundCode(), delta);
        } else if ("REDEEM".equals(tx.getType())) {
            holding.setTotalShares(holding.getTotalShares().subtract(delta));
            holding.setAvailableShares(holding.getAvailableShares().subtract(delta));
            log.info("      [过账] 赎回减仓: Acc={}, Fund={}, -{}", tx.getAccountId(), tx.getFundCode(), delta);
        }
    }
}