-- Миграция для добавления поддержки ролей и уровней рангов
-- Выполнить в PostgreSQL для синхронизации рангов с Discord

-- Добавляем новые колонки в таблицу ranks
ALTER TABLE ranks ADD COLUMN IF NOT EXISTS role_id BIGINT;
ALTER TABLE ranks ADD COLUMN IF NOT EXISTS rank_level INTEGER;

-- Заполняем данными из config.json (на основе предоставленного конфига)
UPDATE ranks SET role_id = 1246114675574313021, rank_level = 1 WHERE name = 'Рядовой';
UPDATE ranks SET role_id = 1246114674638983270, rank_level = 2 WHERE name = 'Ефрейтор';
UPDATE ranks SET role_id = 1261982952275972187, rank_level = 3 WHERE name = 'Мл. Сержант';
UPDATE ranks SET role_id = 1246114673997123595, rank_level = 4 WHERE name = 'Сержант';
UPDATE ranks SET role_id = 1246114672352952403, rank_level = 5 WHERE name = 'Ст. Сержант';
UPDATE ranks SET role_id = 1246114604958879754, rank_level = 6 WHERE name = 'Старшина';
UPDATE ranks SET role_id = 1246114604329865327, rank_level = 7 WHERE name = 'Прапорщик';
UPDATE ranks SET role_id = 1251045305793773648, rank_level = 8 WHERE name = 'Ст. Прапорщик';
UPDATE ranks SET role_id = 1381008703389569166, rank_level = 9 WHERE name = 'Мл. Лейтенант';
UPDATE ranks SET role_id = 1246115365746901094, rank_level = 10 WHERE name = 'Лейтенант';
UPDATE ranks SET role_id = 1246114469340250214, rank_level = 11 WHERE name = 'Ст. Лейтенант';
UPDATE ranks SET role_id = 1381358091555311637, rank_level = 12 WHERE name = 'Капитан';

-- Ранги без ролей в config.json помечаем как неактивные
UPDATE ranks SET rank_level = 13 WHERE name = 'Майор';
UPDATE ranks SET rank_level = 14 WHERE name = 'Подполковник';
UPDATE ranks SET rank_level = 15 WHERE name = 'Полковник';
UPDATE ranks SET rank_level = 16 WHERE name = 'Генерал-майор';
UPDATE ranks SET rank_level = 17 WHERE name = 'Генерал-лейтенант';
UPDATE ranks SET rank_level = 18 WHERE name = 'Генерал-полковник';
UPDATE ranks SET rank_level = 19 WHERE name = 'Генерал Армии';

-- Создаем индекс для быстрого поиска по уровню ранга
CREATE INDEX IF NOT EXISTS idx_ranks_level ON ranks(rank_level);

-- Проверяем результат
SELECT id, name, role_id, rank_level FROM ranks ORDER BY rank_level;