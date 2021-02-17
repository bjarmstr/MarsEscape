'''
Created on Feb. 16, 2021

https://redislabs.com/blog/async-await-programming-basics-python-examples/


'''
import redis
import rconfig as cfg #connection data for redis database

# The operation to perform for each event
def add_new_win(conn, winner):
    print("made it to add winner")
    conn.zincrby('wins_counter', 1, winner)
    conn.incr('total_games_played')

def main():
    # Connect to Redis
    conn = redis.Redis(host=cfg.redis_signin["host"], port=cfg.redis_signin["port"],
                 password=cfg.redis_signin["password"], decode_responses=True)
    # Tail the event stream
    last_id = '$' 
    while True:
        events = conn.xread({'wins_stream': last_id}, block=0, count=10)
        # Process each event by calling `add_new_win`
        print(events)
        for _, e in events:
            winner_dict = ((e[0])[1])
            print(winner_dict,"winner")
            print(type(winner_dict))
            winner = winner_dict['winner']
            add_new_win(conn, winner)
            id_dict = ((e[0])[0])
            print(id_dict)
            last_id = id_dict

if __name__ == '__main__':
    main()
