from telegram.ext import (ApplicationBuilder,
                          CommandHandler, MessageHandler, filters, ContextTypes,
                          ConversationHandler, CallbackQueryHandler)
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
import openai
import logging
import re
import mysql.connector
from dotenv import load_dotenv
import os
import json

ASK_FOR_QUERY, ASK_FOR_ADMIN_PASSWORD, CONFIRM_ADMIN_LOGIN, ASK_FOR_STUDENT_ROLL = range(4)


class AIQuery:
    def __init__(self, query):
        self.user_query = query
        self.user_followup_responses = []
        self.ai_followup_responses = []
        self.more_info_needed = False
        self.sql_queries = []
        self.sql_query_results = []
        self.final_answer = None
        self.infinite_loop = False

    @property
    def formatted_query_text(self):
        return '\n'.join([f'You requested SQL query : \n{sql_query}\nResult of your requested query: \n{query_result}\n\n' for sql_query, query_result in zip(self.sql_queries, self.sql_query_results)])


def parse_response(query, response_text, query_object: AIQuery):
    print(f'In parse response, response_text : {response_text}')
    json_response = json.loads(response_text, strict=False)
    response_type = json_response.get('response_type')

    if response_type is None:
        raise ValueError('Did not find response_type field in OpenAI response')

    query_object.more_info_needed = False

    if response_type == 'more_info':
        query_object.more_info_needed = True
        more_info_text = json_response.get('more_info_text')
        if more_info_text is None:
            raise ValueError('Did not find a match for more_info_text in response!')
        print(f'Appended {more_info_text} to ai_followup responses')
        query_object.ai_followup_responses.append(more_info_text)
        query_object.user_followup_responses.append(query)

    elif response_type == 'sql_queries':
        sql_queries = json_response.get('sql_queries')
        if sql_queries is None:
            raise ValueError('Did not find a match for sql_query in response!')
        for query in sql_queries:
            if query in query_object.sql_queries:
                query_object.infinite_loop = True
                break
        else:
            query_object.sql_queries.extend(sql_queries)

    elif response_type == 'final_answer':
        query_object.final_answer = json_response.get('final_answer')
    else:
        raise ValueError(f'Unknown response type : {response_type}')


async def query_openai_llm(query, query_object: AIQuery):
    print(f'formatted query text : {query_object.formatted_query_text}')

    rules_with_sql = f'''
    RULES :
    There are 3 possibilities
    1. You need more information from the client\n
    You can ask the client for more information, if the client is asking to insert 
    information they MUST provide values for EVERY field\n
    Same goes for other things, like creating tables etc! \n
    For example : 
    client : I want to mark the attendance of a student named "John" for the month of September\n
    your response more_info: "What percentage attendance shall I mark for John and what course are they in?"
    2. You need to perform an SQL query\n
    It may be the case that you require information from the database in order to respond to the client, first look at
    the previous SQL queries you have performed: {query_object.formatted_query_text}\n\n
    Generate more sql queries ONLY if the required information is not present in the previous sql queries..
    Generate the sql queries in a single line ONLY, do NOT generate mutliline sql queries.. fit the query into one line.
    3. You have sufficient information \n
    go ahead and create the final answer in a verbose and cheerful manner.\n
    
    RESPONSE FORMAT :
    you MUST generate the response in the following json format:
    {{"response_type": \"more_info\"/\"sql_queries\"/\"final_answer\"\n
    more_info_text: \"request client for more information according to your needs within quotes\"\n
    sql_queries: ["generate sql query according to the clients needs within double quotes",
    "sql query 2", "sql query 3"...],
    final_answer: \"generate your final answer, be polite and cheerful\"}}\n
    '''
    rules_without_sql = '''
    RULES :
    1. If you need more information you MUST ask the client for more info\n
    if the client is asking to insert information they MUST provide values for EVERY field\n
    Same goes for other things, like creating tables etc!\n
    2. If you have sufficient information go ahead and create the final answer as a politely worded answer.\n
    
    RESPONSE FORMAT :
    you MUST generate the response in the following json format ONLY:
    {{"response_type": \"more_info\"/\"final_answer\"\n
    more_info_text: \"request client for more information according to your needs within quotes\"\n
    final_answer: \"generate your final answer based on the given information and the results of your sql queries, be polite and cheerful\"}}\n
    '''
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system",
             "content": "You are an expert database engineer, you have to  answer the client's queries for the following database:\n"
                        """
                                          mysql> create table administrator(
                                          -> admin_id int,admin_name varchar(20),password int,primary key(admin_id));
                                          
                                          mysql> create table department(
                                          -> dept_id int ,department_name varchar (20),
                                          -> primary key(dept_id));
                                          
                                          mysql> create table student(
                                          -> roll_no int,s_name varchar(20),address varchar(20),cont_no int,primary key(roll_no)), 
                                          -> section_id int references section(section_id),
                                          -> dept_id references department(dept_id);
                                          
                                          mysql> create table registration(
                                          -> reg_id int, foreign key (roll_no) references student(roll_no),
                                          -> primary key(reg_id));
                                          
                                          mysql> create table course(
                                          -> course_id int, c_name varchar (20), dept_id int,
                                          -> foreign key (dept_id) references department(dept_id));
                                                                          
                                          mysql> create table attendance(
                                        -> dept_id int,roll_no int,s_name varchar (20),course varchar(20),percentage int,
                                        -> foreign key (roll_no) references student(roll_no),
                                        -> foreign key (dept_id) references department(dept_id));
                                        
                                        mysql> create table section(
                                        -> section_id int,section_name varchar (20),dept_id int ,
                                        -> primary key(section_id),
                                        -> foreign key (dept_id) references department(dept_id));
                                          
                                        mysql> create table exam(
                                        -> reg_no int,marks int,course varchar(20),
                                        -> dept_id int,
                                        -> primary key(reg_no),
                                        -> foreign key (dept_id) references department(dept_id));
                                          """
                        f"{rules_with_sql if not query_object.infinite_loop else rules_without_sql}"
                        "Your conversation history with the client:\n"
                        f"User responses : {query_object.user_followup_responses}\n"
                        f"Your responses : {query_object.ai_followup_responses}\n\n"


             },
            {"role": "user", "content": f'The client has communicated the following :\n\n'
                                        f'{query}\n\n'
                                        f"Your query history :\n {query_object.formatted_query_text}\n\n"
                                        f'Before generating the information, take a deep breath, look at the rules provided before generating the response, '
                                        f'Now generate ONLY the json response, do not include any additional text besides the json response, {{..'
             },
            {"role": "assistant", "content": ""},
        ]
    )
    response_text = response['choices'][0]['message']['content']
    parse_response(query, response_text, query_object)

    print(response_text)


async def instructions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text('This is a centralised student management system!')


async def ai_sql_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text('You can ask for any information from the database or '
                                              'insert any information into the database in your natural language!\n\n'
                                              'for example: Show all students in division B.')
    return ASK_FOR_QUERY


def evaluate_query(sql_query: str):
    mydb = mysql.connector.connect(
        host="localhost",
        user="root",
        password="manager",
        database="student_management"
    )
    mycursor = mydb.cursor(dictionary=True)
    try:
        mycursor.execute(sql_query)
    except mysql.connector.Error as e:
        mycursor.close()
        return e.msg

    if 'create' in sql_query.lower():
        mydb.commit()
        mycursor.close()
        return f'create operation successful!'

    elif 'drop' in sql_query.lower():
        mydb.commit()
        mycursor.close()
        return f'drop operation successful!'

    elif 'update' in sql_query.lower():
        mydb.commit()
        mycursor.close()
        return f'successfully updated {mycursor.rowcount} row (s)'

    elif 'insert' in sql_query.lower():
        mydb.commit()
        mycursor.close()
        return f'successfully inserted {mycursor.rowcount} row (s)'

    elif 'alter' in sql_query.lower():
        mydb.commit()
        mycursor.close()
        return f'alter operation successful!'

    elif 'delete' in sql_query.lower():
        mydb.commit()
        mycursor.close()
        return f'successfully deleted {mycursor.rowcount} row (s)'

    elif 'select' or 'show' in sql_query.lower():
        results = mycursor.fetchall()
        columns = f"{' '.join(key for key in results[0].keys())}\n"
        mycursor.close()
        return columns + '\n'.join(
            [' '.join([str(element) for element in inner_dict.values()]) for inner_dict in results])

    else:
        mydb.commit()
        mycursor.close()
        return 'operation successful!'


async def query_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.effective_message.text
    query_object: AIQuery = context.user_data.setdefault('query_info', AIQuery(query=query))
    await query_openai_llm(query, query_object=query_object)
    print(f'ai_followup responses : {query_object.ai_followup_responses}')
    print(f'user_followup responses : {query_object.user_followup_responses}')
    print(f'ai_sql_queries : {query_object.sql_queries}')
    print(f'sql_query_results : {query_object.sql_query_results}')

    if query_object.more_info_needed:
        await update.effective_message.reply_text(query_object.ai_followup_responses[-1])
        return ASK_FOR_QUERY

    elif query_object.final_answer is not None:
        await update.effective_message.reply_text(
            f'Here is the result of your query:\n\n{query_object.final_answer}\n\nTo start a new query use command /aiquery')
        context.user_data.clear()
        return ConversationHandler.END

    for query in query_object.sql_queries:
        query_object.sql_query_results.append(evaluate_query(query))

    return await query_received(update, context)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_message.reply_text(f'Successfully cancelled!')
    return ConversationHandler.END


def get_admin_information(admin_id: int):
    mydb = mysql.connector.connect(
        host="localhost",
        user="root",
        password="manager",
        database="student_management"
    )
    mycursor = mydb.cursor(dictionary=True)
    mycursor.execute('select * from administrator where admin_id = %s', (admin_id,))
    results = mycursor.fetchall()[0]
    mycursor.close()

    return results


def get_student_information(student_id: int):
    mydb = mysql.connector.connect(
        host="localhost",
        user="root",
        password="manager",
        database="student_management"
    )
    mycursor = mydb.cursor(dictionary=True)
    mycursor.execute('select * from student where roll_no = %s', (student_id,))
    results = mycursor.fetchall()
    mycursor.close()

    return results[0] if len(results) > 0 else None


async def send_admin_info(update: Update, context: ContextTypes.DEFAULT_TYPE, admin_config):
    admin_id = admin_config['admin_id']
    admin_info = get_admin_information(admin_id)
    reply_markup = InlineKeyboardMarkup.from_row([InlineKeyboardButton(text='Logout', callback_data='logout_admin')])
    await update.effective_user.send_message(text=f'Logged in as administrator {admin_info["admin_name"]}! \n\n'
                                                  f'use /aiquery to make changes to the database.',
                                             reply_markup=reply_markup)


async def send_student_info(update: Update, context: ContextTypes.DEFAULT_TYPE, student_config):
    student_id = student_config['roll_no']
    student_info = get_student_information(student_id)
    reply_markup = InlineKeyboardMarkup.from_row([InlineKeyboardButton(text='Logout', callback_data='logout_student')])
    await update.effective_user.send_message(text=f'Logged in as student {student_info["s_name"]}! \n\n' if student_info is not None else 'We could not find you in our database!',
                                             reply_markup=reply_markup if student_info is not None else None)


async def send_login_prompt(update, context):
    reply_markup = InlineKeyboardMarkup.from_row(
        [InlineKeyboardButton(text='Login as Admin', callback_data='login_as_admin'),
         InlineKeyboardButton(text='Login as Student', callback_data='login_as_student')])
    await update.effective_user.send_message(
        text=f'This is a centralised student management system created by A3 batch students!\n\n'
             f'You need to login as an admin or student!', reply_markup=reply_markup)


async def check_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        with open(f'administrators/{update.effective_user.id}.json', 'r') as f:
            admin_config = json.load(f)
            await send_admin_info(update, context, admin_config)
            return
    except FileNotFoundError:
        pass

    try:
        with open(f'students/{update.effective_user.id}.json', 'r') as f:
            student_config = json.load(f)
            await send_student_info(update, context, student_config)
            return
    except FileNotFoundError:
        pass

    await send_login_prompt(update, context)
    return


async def login_as_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_user.send_message(text='Please enter your name!')
    await update.callback_query.answer()
    return ASK_FOR_ADMIN_PASSWORD


async def admin_name_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['admin_name'] = update.effective_message.text
    await update.effective_user.send_message(text='Please enter your password!')
    return CONFIRM_ADMIN_LOGIN


def check_admin_exists(admin_name, admin_password):
    mydb = mysql.connector.connect(
        host="localhost",
        user="root",
        password="manager",
        database="student_management"
    )
    mycursor = mydb.cursor(dictionary=True)
    mycursor.execute('select admin_id from administrator where admin_name = %s and password = %s',
                     (admin_name, admin_password))
    results = mycursor.fetchall()
    mycursor.close()

    return results[0] if len(results) > 0 else False

def check_student_exists(student_roll):
    mydb = mysql.connector.connect(
        host="localhost",
        user="root",
        password="manager",
        database="student_management"
    )
    mycursor = mydb.cursor(dictionary=True)
    mycursor.execute('select admin_id from administrator where roll_no = %s',
                     (student_roll,))
    results = mycursor.fetchall()
    mycursor.close()

    return results[0] if len(results) > 0 else False


async def confirm_admin_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    admin_password = update.effective_message.text
    admin_name = context.user_data.pop('admin_name')
    login_id = check_admin_exists(admin_name, admin_password)

    if not login_id:
        await update.effective_user.send_message('We could not confirm your login!')
    else:
        with open(f'administrators/{update.effective_user.id}.json', 'w') as f:
            json.dump({'admin_id': login_id['admin_id']}, f)
        await send_admin_info(update, context, {'admin_id': login_id['admin_id']})
    return ConversationHandler.END


async def login_as_student(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.effective_user.send_message(text='Please enter your roll no!')
    await update.callback_query.answer()
    return ASK_FOR_STUDENT_ROLL


async def confirm_student_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    student_roll_no = update.effective_message.text
    student_exists = check_student_exists(student_roll_no)

    with open(f'students/{update.effective_user.id}.json', 'w+') as f:
        json.dump({'roll_no': student_roll_no}, f)
    await send_student_info(update, context, {'roll_no': student_roll_no})

    return ConversationHandler.END


async def logout_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    os.remove(f'administrators/{update.effective_user.id}.json')
    await update.effective_user.send_message('Successfully logged out as admin!')
    await send_login_prompt(update, context)
    await update.callback_query.answer()


async def logout_student(update: Update, context: ContextTypes.DEFAULT_TYPE):
    os.remove(f'students/{update.effective_user.id}.json')
    await update.effective_user.send_message('Successfully logged out as student!')
    await send_login_prompt(update, context)
    await update.callback_query.answer()


def create_app(bot_token, openai_token):
    openai.api_key = openai_token
    new_application = (
        ApplicationBuilder()
        .token(bot_token)
        .build()
    )
    _set_logging()
    return new_application


def add_handlers(application):
    application.add_handler(CommandHandler('start', check_login))
    application.add_handler(ConversationHandler(entry_points=[CommandHandler('aiquery', ai_sql_entry)],
                                                states={ASK_FOR_QUERY: [MessageHandler(filters.TEXT, query_received),
                                                                        CommandHandler('cancel', cancel)]},
                                                fallbacks=[],
                                                per_chat=True
                                                ))
    application.add_handler(
        ConversationHandler(entry_points=[CallbackQueryHandler(pattern='login_as_admin', callback=login_as_admin),
                                          CallbackQueryHandler(pattern='login_as_student', callback=login_as_student)],
                            states={ASK_FOR_ADMIN_PASSWORD: [MessageHandler(filters.TEXT, admin_name_received),
                                                             CommandHandler('cancel', cancel)],
                                    CONFIRM_ADMIN_LOGIN: [MessageHandler(filters.TEXT, confirm_admin_login),
                                                          CommandHandler('cancel', cancel)],
                                    ASK_FOR_STUDENT_ROLL: [MessageHandler(filters.TEXT, confirm_student_login),
                                                           CommandHandler('cancel', cancel)]},
                            fallbacks=[],
                            per_chat=True
                            ))
    application.add_handler(CallbackQueryHandler(pattern='logout_admin', callback=logout_admin))
    application.add_handler(CallbackQueryHandler(pattern='logout_student', callback=logout_student))
    application.add_handler(MessageHandler(filters.ChatType.PRIVATE & filters.TEXT, instructions))


def _set_logging():
    logging.basicConfig(
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        level=logging.INFO
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)


if __name__ == '__main__':
    load_dotenv('secrets/secrets.env')
    bot_token = os.getenv('BOT_TOKEN')
    open_ai_key = os.getenv('OPENAI_API_KEY')
    app = create_app(bot_token=bot_token, openai_token=open_ai_key)
    add_handlers(app)
    app.run_polling()