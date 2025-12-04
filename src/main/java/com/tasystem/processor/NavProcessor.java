package com.tasystem.processor;

import com.tasystem.model.FundNav;
import com.tasystem.model.MonitorTask;
import com.tasystem.repository.MonitorRepository;
import lombok.extern.slf4j.Slf4j;
import org.apache.commons.csv.CSVFormat;
import org.apache.commons.csv.CSVParser;
import org.apache.commons.csv.CSVRecord;

import java.io.FileReader;
import java.io.Reader;
import java.math.BigDecimal;
import java.time.LocalDate;

@Slf4j
public class NavProcessor extends BaseProcessor {

    @Override
    protected void processLogic(MonitorTask task) throws Exception {
        MonitorRepository repo = MonitorRepository.getInstance();
        
        CSVFormat format = CSVFormat.DEFAULT.builder()
                .setHeader()
                .setSkipHeaderRecord(true)
                .build();

        try (Reader reader = new FileReader(task.getFullPath());
             CSVParser parser = new CSVParser(reader, format)) {
            
            for (CSVRecord r : parser) {
                String code = r.get("fund_code");
                BigDecimal nav = new BigDecimal(r.get("nav"));
                
                repo.getNavTable().put(code, FundNav.builder()
                        .fundCode(code)
                        .nav(nav)
                        .date(LocalDate.now())
                        .build());
                
                log.info("   -> [行情] {} 净值更新: {}", code, nav);
            }
        }
    }
}