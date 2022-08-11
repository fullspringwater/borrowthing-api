import datetime
from flask import request
from flask_jwt_extended import create_access_token, get_jwt, jwt_required, get_jwt_identity
from flask_restful import Resource
from mysql_connection import get_connection
import mysql.connector

from email_validator import validate_email, EmailNotValidError

from utils import check_password, hash_password

class UserRegisterResource(Resource) :
    # 회원가입하기
    def post(self) :
        
    #    {
    #       "email" : "abc@naver.com",
    #       "password" : "1234",
    #       "name" : "홍길동",
    #       "phoneNumber" : "010-1234-1234",
    #       "nickname" : "홍길동"
    #     }

        # 1. 클라이언트가 body 에 보내준 json 을 받아온다.
        data = request.get_json()

        # 2. 이메일 주소형식이 제대로 된 주소형식인지
        # 확인하는 코드 작성.

        try :
            validate_email( data['email'] )
        except EmailNotValidError as e:
            # email is not valid, exception message is human-readable
            print(str(e))
            return {'error' : str(e)} , 400        
        
        # 3. 비밀번호의 길이가 유효한지 체크한다.
        # 비번길이는 4자리 이상, 12자리 이하로만!
        if len(data['password']) < 4 or len(data['password']) > 12 :
            return {'error' : '비밀번호 길이를 확인하세요'}, 400

        # 4. 비밀번호를 암호화 한다.
        hashed_password = hash_password( data['password'] )

        print(hashed_password)

        # 5. 데이터베이스에 회원정보를 저장한다!!
        try :
            # 데이터 insert 
            # 1. DB에 연결
            connection = get_connection()

            # 5-1. 쿼리문 만들기
            query = '''insert into users
                    (email, password, name, phoneNumber, nickname)
                    values
                    (%s, %s , %s, %s, %s);'''
            
            record = (data['email'], hashed_password, data['name'],
            data['phoneNumber'], data['nickname'])

            # 5-2. 커서를 가져온다.
            cursor = connection.cursor()

            # 5-3. 쿼리문을 커서를 이용해서 실행한다.
            cursor.execute(query, record)

            # 5-4. 커넥션을 커밋해줘야 한다 => 디비에 영구적으로 반영하라는 뜻
            connection.commit()

            # 5-5. 디비에 저장된 아이디값 가져오기.
            user_id = cursor.lastrowid

            # 6. 데이터 가져오기
            result_list = cursor.fetchall()

            # 6-1. 문자열로 바꿔서 다시 저장하기
            i = 0
            for record in result_list :
                result_list[i]['createdAt'] = record['createdAt'].isoformat()
                i = i + 1

            # 6. 자원 해제
            cursor.close()
            connection.close()

        except mysql.connector.Error as e :
            print(e)
            cursor.close()
            connection.close()
            return {"error" : str(e)}, 503

        # user_id 를 바로 보내면 안되고,
        # JWT 로 암호화 해서 보내준다.
        # 암호화 하는 방법

        # 억세스 토큰 만료기간 설정하는 방법
        access_token = create_access_token(user_id, 
                        expires_delta=datetime.timedelta(minutes=1))

        return {'result' : 'success'}, 200

class UserLoginResource(Resource) :
    # 로그인하기
    def post(self) :
        # 1. 클라이언트로부터 body로 넘어온 데이터를 받아온다.
        # {
        #     "email": "abc@naver.com",
        #     "password": "1234"
        # }

        data = request.get_json()

        # 2. 이메일로, DB에 이 이메일과 일치하는 데이터를
        # 가져온다.

        try :
            connection = get_connection()

            query = '''select *
                    from users
                    where email = %s;'''

            record = (data['email'] , )
            
            # select 문은, dictionary = True 를 해준다.
            cursor = connection.cursor(dictionary = True)

            cursor.execute(query, record)

            # select 문은, 아래 함수를 이용해서, 데이터를 가져온다.
            result_list = cursor.fetchall()

            print(result_list)

            # 중요! 디비에서 가져온 timestamp 는 
            # 파이썬의 datetime 으로 자동 변경된다.
            # 문제는! 이데이터를 json 으로 바로 보낼수 없으므로,
            # 문자열로 바꿔서 다시 저장해서 보낸다.
            i = 0
            for record in result_list :
                result_list[i]['createdAt'] = record['createdAt'].isoformat()
                i = i + 1

            cursor.close()
            connection.close()

        except mysql.connector.Error as e :
            print(e)
            cursor.close()
            connection.close()

            return {"error" : str(e)}, 503

        
        # 3. result_list 의 행의 갯수가 1개이면,
        # 유저 데이터를 정상적으로 받아온것이고
        # 행의 갯수가 0이면, 요청한 이메일은, 회원가입이
        # 되어 있지 않은 이메일이다.

        if len(result_list) != 1 :
            return {'error' : '등록되어 있지 않은 이메일입니다.'}, 400

        # 4. 비밀번호가 맞는지 확인한다.
        user_info = result_list[0]

        # data['password'] 와 user_info['password']를 비교

        check = check_password(data['password'] , user_info['password'])

        if check == False :
            return {'error' : '비밀번호가 맞지 않습니다.'}

        access_token = create_access_token( user_info['id'])

        return {'result' : 'success', 
                'access_token' : access_token}, 200

jwt_blacklist = set()

class UserLogoutResource(Resource) :
    @jwt_required()
    # 로그아웃하기
    def post(self) :

        jti = get_jwt()['jti']
        print(jti)
        
        jwt_blacklist.add(jti)

        return {'result' : 'success'}, 200

class UserEditResource(Resource) :
    @jwt_required()
    # 내 정보 수정하기
    def put(self):
        # 1. 클라이언트로부터 데이터를 받아온다.
        # {
        #     "title": "점심먹자",
        #     "date": "2022-07-10 14:00",
        #     "content": "짜장면"
        # }
        data = request.get_json()
        user_id = get_jwt_identity()

        hashed_password = hash_password( data['password'] )

        # 2. 디비 업데이트
        try :
            # 데이터 업데이트 
            # 1. DB에 연결
            connection = get_connection()

            # 2. 쿼리문 만들기
            query = '''update users 
                    set nickname = %s, password = %s
                    where id = %s;'''
            
            record = (data["nickname"], hashed_password, user_id)

            # 3. 커서를 가져온다.
            cursor = connection.cursor()

            # 4. 쿼리문을 커서를 이용해서 실행한다.
            cursor.execute(query, record)

            # 5. 커넥션을 커밋해줘야 한다 => 디비에 영구적으로 반영하라는 뜻
            connection.commit()

            # 6. 자원 해제
            cursor.close()
            connection.close()

        except mysql.connector.Error as e :
            print(e)
            cursor.close()
            connection.close()
            return {'error' : str(e)}, 503


        return {'result' : 'success'}, 200

