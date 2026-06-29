import os
import pandas as pd
from sqlalchemy import create_engine
import re
import shutil

# Настройки подключения к PostgreSQL
DB_PASS = os.getenv('DB_PASSWORD')
DB_URL = f"postgresql://admin:{DB_PASS}@db:5432/inventory_db"
engine = create_engine(DB_URL)

def process_inventory_files():
    inbox_path = '/app/inbox'
    archive_path = '/app/archive'
    
    if not os.path.exists(inbox_path):
        print(f"❌ Папка {inbox_path} не найдена.")
        return

    files = [f for f in os.listdir(inbox_path) if f.endswith(('.xlsx', '.xls'))]
    
    if not files:
        print("📥 Новых файлов в inbox нет.")
        return

    for file in files:
        file_path = os.path.join(inbox_path, file)
        print(f"🚀 Обработка файла: {file}")
        
        try:
            # 1. Читаем шапку для извлечения метаданных
            header_df = pd.read_excel(file_path, nrows=7, header=None)
            
            # Извлекаем Номер и Дату из первой строки
            doc_info = str(header_df.iloc[0, 2])
            doc_num = re.search(r'МТ-\d+', doc_info).group(0) if re.search(r'МТ-\d+', doc_info) else "Б/Н"
            doc_date_raw = re.search(r'\d{2}\.\d{2}\.\d{4}', doc_info).group(0) if re.search(r'\d{2}\.\d{2}\.\d{4}', doc_info) else None
            
            # Находим Склад
            warehouse_raw = str(header_df.iloc[2, 7])
            warehouse = warehouse_raw.replace('Склад:', '').strip()
            
            # Находим Ответственного
            resp_raw = str(header_df.iloc[5, 7])
            responsible = resp_raw.replace('Ответственный:', '').strip()

            # 2. Читаем основную таблицу
            df = pd.read_excel(file_path, skiprows=8, header=None)

            # 3. Целевые колонки (C, N, S, U, W, Y, Z)
            target_indices = [2, 13, 18, 20, 22, 24, 25]
            
            # Оставляем только нужные колонки
            df_final = df.iloc[:, target_indices].copy()
            df_final.columns = [
                'product_name', 'product_code', 'stock_accounting', 
                'stock_fact', 'stock_deviation', 'price_buy', 'price_retail'
            ]

            # 4. Очистка данных
            df_final = df_final.dropna(subset=['product_name'])
            df_final = df_final[~df_final['product_name'].str.contains('Итого|Всего|Товар', na=False)]

            # 5. Привязка метаданных
            if doc_date_raw:
                # Превращаем строку в объект даты (БЕЗ .dt)
                clean_date = pd.to_datetime(doc_date_raw, dayfirst=True).date()
            else:
                clean_date = None
                
            df_final['doc_date'] = clean_date
            df_final['doc_number'] = doc_num
            df_final['warehouse'] = warehouse
            df_final['responsible'] = responsible
            df_final['source_file'] = file

            # 6. Загрузка в PostgreSQL
            # Импортируем тип Date для SQLAlchemy внутри функции
            from sqlalchemy import Date
            
            df_final.to_sql(
                'inventory_data', 
                engine, 
                if_exists='append', 
                index=False,
                dtype={'doc_date': Date} # Принудительно создаем колонку типа DATE (без времени)
            )

            # 7. Делаем перемещение в архив
            shutil.move(file_path, os.path.join(archive_path, file))
            print(f"✅ Успешно загружено {len(df_final)} позиций.")

        except Exception as e:
            print(f"❌ Ошибка в файле {file}: {str(e)}")

# Вызываем функцию
if __name__ == "__main__":
    process_inventory_files()