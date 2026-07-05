WITH RankedRows AS (
    SELECT 
        id, 
        text, 
        region,
		cityname,
		citytype,
		district,
		street,
		bldnum,
		bldlist,
		key,
        COUNT(*) OVER (PARTITION BY text, region, cityname, citytype, district, street, bldnum, bldlist) as group_count
    FROM 
        addr_texts
	WHERE key < 522
)
SELECT *
FROM 
    RankedRows
WHERE 
    group_count > 1;
