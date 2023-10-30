import os

from django.shortcuts import render
from django.http import JsonResponse
import requests
import json
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.http import HttpResponse
from django.views import View
from home import models
from home import tokens

from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain.llms import OpenAI
from langchain.chains import ConversationChain
from langchain.chat_models import ChatOpenAI


# Create your views here.

# return HttpResponse("HttpResponse : /home/templates/welcome_home.html.")

# return HttpResponse("HttpResponse : /home/templates/home.html.")
def main_home(request):
    return render(request, 'home.html')


@method_decorator(csrf_exempt, name='dispatch')
def kakaoLogin(request):
    if (request.method == 'GET'):
        url = os.getenv('KAKAO_URL')
        return JsonResponse({'message': 'SUCCESS', 'result': url}, status=200)
    else:
        return JsonResponse({'message': 'INVALID_HTTP_METHOD'}, status=405)


class KakaoCallbackView(View):
    def get(self, request, *args, **kwargs):
        code = request.GET.get('code', '')

        data = {
            "grant_type": 'authorization_code',
            "client_id": os.getenv('KAKAO_KEY'),
            "redirection_url": os.getenv('REDIRECT_URL'),
            "code": code
        }
        kakao_token_api = "https://kauth.kakao.com/oauth/token"
        access_token = requests.post(kakao_token_api, data=data).json()["access_token"]

        kakao_user_api = "https://kapi.kakao.com/v2/user/me"
        header = {"Authorization": f"Bearer ${access_token}"}
        user_information = requests.get(kakao_user_api, headers=header).json()
        kakao_id = user_information["id"]
        kakao_nickname = user_information["properties"]["nickname"]

        models.saveUserInfo(kakao_id, kakao_nickname)

        user_token = tokens.generate_token(kakao_id)
        return JsonResponse({'message': 'SUCCESS', 'token': user_token}, status=200)


@method_decorator(csrf_exempt, name='dispatch')
def dbSearch(request):
    if (request.method == 'POST'):
        data = json.loads(request.body)
        category = data["search_category"]
        keyword = data["food_keyword"]
        if not category or not keyword:
            return JsonResponse({'message': 'NO_KEY'}, status=400)
        res = models.food_search(category, keyword)
        if not res:
            return JsonResponse({'message': 'NOT_IN_DB'}, status=400)
        else:
            return JsonResponse({'message': 'SUCCESS', 'result': res}, status=200)
    else:
        return JsonResponse({'message': 'INVALID_HTTP_METHOD'}, status=405)


tag = ''
keyword = ''


def rcpHandler():
    global tag, keyword
    if tag == 'name':
        url = os.getenv('FOOD_URL') + os.getenv('RCP_NAME') + keyword
    elif tag == 'type':
        url = os.getenv('FOOD_URL') + os.getenv('RCP_TYPE') + keyword
    response = requests.get(url)
    res = json.loads(response.text)
    rcp = res['COOKRCP01']
    return rcp


@method_decorator(csrf_exempt, name='dispatch')
def apiSearch(request):
    if (request.method == 'GET'):
        global tag, keyword
        keyword = request.GET.get('keyword')
        tag = request.GET.get('tag')
        if not keyword or not tag:
            return JsonResponse({'message': 'NO_KEY'}, status=400)
        try:
            rcp = rcpHandler()
        except:
            return JsonResponse({'message': 'API_ERR'}, status=404)
        msg = rcp['RESULT']['MSG']

        if rcp['total_count'] == '0':
            return JsonResponse({'message': msg}, status=400)
        else:
            count = rcp['total_count']

        rcp_row = rcp['row']
        rowsList = []
        for row in rcp_row:
            name = row.get('RCP_NM', None)
            image = row.get('ATT_FILE_NO_MK', None)
            seq = row.get('RCP_SEQ', None)
            rowsList.append({'name': name, 'image': image, 'seq': seq})
            # 음식 명으로만 검색할 경우 여러가지 값이 해당 명이 포함된 다른 음식들도 검색되기 때문에 일련번호(seq)로 레시피와 영양정보를 알아낼 수 있도록 함
        return JsonResponse({'message': msg, 'total_count': count, 'row': rowsList}, status=200)
    else:
        return JsonResponse({'message': 'INVALID_HTTP_METHOD'}, status=405)


@method_decorator(csrf_exempt, name='dispatch')
def foodDetail(request):
    if (request.method == 'GET'):
        global keyword, tag
        recipe_seq = request.GET.get('seq')
        if not keyword or not tag or not recipe_seq:
            return JsonResponse({'message': 'NO_KEY'}, status=400)
        try:
            rcp = rcpHandler()
        except:
            return JsonResponse({'message': 'API_ERR'}, status=404)

        if rcp['total_count'] == '0':
            result = rcp['RESULT']
            return JsonResponse({'message': result['MSG']}, status=400)

        rcp_row = rcp['row']
        nutritionList = []
        recipeList = []
        for row in rcp_row:
            seq = row.get('RCP_SEQ', None)
            if seq == recipe_seq:
                name = row.get('RCP_NM', None)
                # 일련번호(seq)로 구분
                eng = row.get('INFO_ENG', None)+"kcal"
                car = row.get('INFO_CAR', None)+"g"
                pro = row.get('INFO_PRO', None)+"g"
                fat = row.get('INFO_FAT', None)+"g"
                na = row.get('INFO_NA', None)+"g"
                nutritionList.append({'열량': eng, '탄수화물': car, '단백질': pro, '지방': fat, '나트륨': na})

                dtls = row.get('RCP_PARTS_DTLS', None)
                tip = row.get('RCP_NA_TIP', None)
                recipe = {'재료정보': dtls}
                for i in range(1, 21):
                    man = row.get(f'MANUAL{i:02}', None)
                    img = row.get(f'MANUAL_IMG{i:02}', None)
                    if man :
                        recipe[f'만드는법_{i:02}'] = man
                    if img :
                        recipe[f'만드는법_이미지_{i:02}'] = img
                recipe['저감 조리법 TIP'] = tip
                recipeList.append(recipe)
                break
        if not recipeList:
            return JsonResponse({'message': 'NO_MATCHING_SEQ'}, status=400)
        return JsonResponse({'message': '1인분 레시피', '메뉴명': name, '영양성분': nutritionList, '레시피': recipeList}, status=200)
    else:
        return JsonResponse({'message': 'INVALID_HTTP_METHOD'}, status=405)


@method_decorator(csrf_exempt, name='dispatch')
def verify_token(request):
    if (request.method == 'GET'):
        access_token = request.GET.get('access_token')
        if not access_token:
            return JsonResponse({'message': 'NOT_FOUND_TOKEN'}, status=400)
        res = tokens.verify_token(access_token)
        if res == "SUCCESS":
            return JsonResponse({'message': res}, status=200)
        else:
            return JsonResponse({'message': res}, status=401)
    else:
        return JsonResponse({'message': 'INVALID_HTTP_METHOD'}, status=405)


@method_decorator(csrf_exempt, name='dispatch')
def token_refresh(request):
    if(request.method == 'POST'):
        data = json.loads(request.body)
        refresh_token = data["refresh_token"]
        if not refresh_token:
            return JsonResponse({'message': 'NOT_FOUND_TOKEN'}, status=400)
        res = tokens.refresh(refresh_token)
        return JsonResponse(res, status=401)
    else:
        return JsonResponse({'message': 'INVALID_HTTP_METHOD'}, status=405)



chat_model = ChatOpenAI()

os.environ["OPENAI_API_KEY"] = os.getenv('OPENAI_API_KEY')

@method_decorator(csrf_exempt, name='dispatch')
def food_recommendation(request):
    if (request.method == 'GET'):
        user_input = request.GET.get('user_input')
        if not user_input:
            return JsonResponse({'message': 'NO_KEY'}, status=400)
        if user_input == '종료':
            return JsonResponse({'message': 'SUCCESS', 'result': '종료'}, status=200)
        try:
            prompt = PromptTemplate(
                user_input = ['user_input'],
                template= "{user_input}을 좋아하는 사람에게 추천할 만한 음식을 추천해줘."
            )

            llm = OpenAI(temperature=0.8)

            user_input = user_input.replace(" ", "")
            user_input = user_input.replace("\n", "")
            user_input = user_input.replace("\t", "")
            user_input = user_input.replace("\'", "")
            user_input = user_input.replace("\"", "")
            user_input = user_input.replace("\r", "")

            chain = LLMChain(llm=llm, prompt=prompt)

            chain.run("호불호 없는 맛있는 음식")

            result = (prompt.format(chain.run))

            return JsonResponse({'message': 'SUCCESS', 'result': result}, status=200)
        except:
            return JsonResponse({'message': 'INCORRECT_API_KEY'}, status=405)

    else:
        return JsonResponse({'message': 'INVALID_HTTP_METHOD'}, status=405)


@method_decorator(csrf_exempt, name='dispatch')
def food_assistance(request):
    if (request.method == 'GET'):
        try:
            llm = OpenAI(temperature=0)
            conversation = ConversationChain(llm=llm, verbose=True)

            user_input = request.GET.get('user_input')

            while True:
                if user_input == '종료':
                    break
                output = conversation.predict(user_input)
                return JsonResponse({'message': 'SUCCESS', 'result': output}, status=200)
        except:
            return JsonResponse({'message': 'INCORRECT_API_KEY'}, status=405)
    else:
        return JsonResponse({'message': 'INVALID_HTTP_METHOD'}, status=405)
