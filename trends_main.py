#!/usr/bin/env python3
import datetime
import pandas as pd
pd.set_option('future.no_silent_downcasting', True)
from pytrends.request import TrendReq
import time  # Импортируем модуль time для задержки
from pytrends.exceptions import TooManyRequestsError  # Импортируем исключение

from pinterest_data import fetch_pinterest_trends

def analyze_trends_with_google(trends_list):
    """Разбивает список трендов на группы, анализирует каждую группу в Google Trends 
    с учётом повторных попыток (TooManyRequestsError) и задержек."""
    
    pytrends = TrendReq(hl='en-US', tz=360)
    batch_size = 5
    all_trends_analysis = []

    for i in range(0, len(trends_list), batch_size):
        queries = trends_list[i:i + batch_size]
        print(f"\nАнализ группы {i // batch_size + 1}: {queries}")
        
        if not queries:
            continue

        max_retries = 3
        retry_delay = 60
        request_delay = 2

        # Попытки запросить Google Trends
        for attempt in range(max_retries):
            try:
                time.sleep(request_delay)
                pytrends.build_payload(kw_list=queries, timeframe='today 3-m', geo='', gprop='')
                
                time.sleep(request_delay)
                interest_over_time_df = pytrends.interest_over_time()
                break
            except TooManyRequestsError:
                if attempt < max_retries - 1:
                    print(f"Слишком много запросов. Попытка {attempt + 1} из {max_retries}.")
                    print(f"Ожидание {retry_delay} секунд перед повторной попыткой...")
                    time.sleep(retry_delay)
                else:
                    print("Превышено максимальное количество попыток. Попробуйте позже.")
                    return
            except Exception as e:
                print(f"Произошла неожиданная ошибка: {str(e)}")
                return

        if interest_over_time_df.empty:
            print("Google Trends не вернул данных по данным запросам.")
            return

        # Готовим данные для расчётов
        interest_over_time_df.reset_index(inplace=True)
        cutoff = interest_over_time_df['date'].max() - datetime.timedelta(days=15)
        first_period = interest_over_time_df[interest_over_time_df['date'] < cutoff]
        second_period = interest_over_time_df[interest_over_time_df['date'] >= cutoff]

        trends_analysis = []
        for q in queries:
            first_avg = first_period[q].mean() if not first_period.empty else 0
            second_avg = second_period[q].mean() if not second_period.empty else 0
            growth = ((second_avg - first_avg) / first_avg) * 100 if first_avg > 0 else 0
            trends_analysis.append((q, first_avg, second_avg, growth))
        
        all_trends_analysis.extend(trends_analysis)

        # Пауза между группами
        if i + batch_size < len(trends_list):
            print("Пауза между запросами...")
            time.sleep(request_delay * 2)

    # Итоговая таблица
    trends_df = pd.DataFrame(all_trends_analysis, columns=["Query", "Avg_Early", "Avg_Recent", "Growth_%"])
    trends_df.sort_values(by="Growth_%", ascending=False, inplace=True)

    print("\nИтоговый анализ динамики интереса ко всем темам:")
    print(trends_df)

if __name__ == "__main__":
    # Получаем тренды с Pinterest
    pinterest_trends = fetch_pinterest_trends()
    print("\nПолученные тренды с Pinterest:")
    print(pinterest_trends)
    
    # Анализируем их через Google Trends
    analyze_trends_with_google(pinterest_trends)