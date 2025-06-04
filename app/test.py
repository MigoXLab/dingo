import asyncio
import time

import aiohttp

url = 'https://labelu-tools.shlab.tech/?tool=extract'
total_requests = 6000  # 总请求数
concurrent_requests_list = [1000]  # 不同的并发请求数


async def make_request(session):
    try:
        async with session.get(url) as response:
            await response.text()
            return response.status == 200
    except Exception as e:
        print(f"请求失败: {str(e)}")
        return False


async def run_test(concurrent_requests):
    start_time = time.time()
    successful = 0
    failed = 0

    async with aiohttp.ClientSession() as session:
        tasks = []
        for _ in range(total_requests):
            task = asyncio.create_task(make_request(session))
            tasks.append(task)
            if len(tasks) >= concurrent_requests:
                results = await asyncio.gather(*tasks)
                successful += sum(results)
                failed += len(results) - sum(results)
                tasks = []

        if tasks:
            results = await asyncio.gather(*tasks)
            successful += sum(results)
            failed += len(results) - sum(results)

    end_time = time.time()
    duration = end_time - start_time

    print(f"\n并发请求数: {concurrent_requests}")
    print(f"总请求数: {total_requests}")
    print(f"成功请求: {successful}")
    print(f"失败请求: {failed}")
    print(f"总耗时: {duration:.2f} 秒")
    print(f"平均每秒处理请求数: {total_requests / duration:.2f}")


async def main():
    for concurrent_requests in concurrent_requests_list:
        await run_test(concurrent_requests)


if __name__ == '__main__':
    asyncio.run(main())
