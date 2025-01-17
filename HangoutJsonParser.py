#!/usr/bin/python3 -Bubb
import argparse, datetime, hashlib, json, os

def parseData():
    global gaia_to_name
    # First pass just to collect names, to deal with issue in the Hangouts.json, where some conversations lack a name for a user, when others show the name correctly.
    gaia_to_name = {}
    for orig_conv in jsonData['conversations']:
        for participant in orig_conv['conversation']['conversation']['participant_data']:
            assert participant['id']['gaia_id'] == participant['id']['chat_id']
            if 'fallback_name' in participant:
                gaia_to_name[participant['id']['gaia_id']] = participant['fallback_name']

    for orig_conv in jsonData['conversations']:
        conversation = {
            'chatName': '',
            'participants': [
                {
                    'id': participant['id']['gaia_id'],
                    'name': participant.get('fallback_name')
                }
                for participant in
                orig_conv['conversation']['conversation']['participant_data']
            ],
            'messages': []
        }

        for event in orig_conv['events']:
            def get_readable_content(event):
                match event['event_type']:
                    case 'REGULAR_CHAT_MESSAGE':
                        content = ''
                        # if it's a message(normal hangouts, image...)
                        for msg_k,msg_v in event['chat_message']['message_content'].items():
                            match msg_k:
                                case 'segment': # if it's a normal hangouts message
                                    for segment in msg_v:
                                        match segment['type']:
                                            case 'TEXT'|'LINK':
                                                content += segment['text']
                                            case 'LINE_BREAK':
                                                content += '\n'
                                            case _: raise segment
                                case 'attachment':
                                    for att in msg_v:
                                        match att['embed_item']['type']:
                                            case ['PLUS_PHOTO']:
                                                content += ' [attachment '+att['embed_item']['plus_photo']['url']+' ]'
                                            case ['PLACE_V2', 'THING_V2', 'THING']:
                                                content += ' [place '+', '.join(k+' '+repr(v) for k,v in att['embed_item']['place_v2'].items())+']'
                                            case ['DYNAMITE_MESSAGE_METADATA']:
                                                content += ' [upload_metadata '+repr(att['embed_item']['dynamite_message_metadata'])+']'
                                            case _: raise Exception('unhandled attachment '+json.dumps(att,indent=4))
                                case _: raise msg_k
                        return content
                    case 'HANGOUT_EVENT':
                        return event['event_type']+' '+event['hangout_event']['event_type']
                    case 'ADD_USER'|'REMOVE_USER':
                        ret = (
                            event['event_type']+' '+event['membership_change'].pop('type')+' '+event['membership_change'].pop('leave_reason')+' '+
                            ' '.join(repr(getName(i['gaia_id'],conversation)) for i in event['membership_change'].pop('participant_id'))
                        )
                        assert event['membership_change'] == {}
                        return ret
                    case 'GROUP_LINK_SHARING_MODIFICATION':
                        return event['event_type']+' '+repr( event['group_link_sharing_modification'])
                    case 'RENAME_CONVERSATION':
                        return event['event_type']+' '+repr(event['conversation_rename'])
                    case _: raise Exception('unhandled event type '+event['event_type'])

            conversation['messages'].append({
                'sender': {
                    'name': getName(event['sender_id']['gaia_id'],conversation),
                    'id':   event['sender_id']['gaia_id']
                },
                'unixtime': int(event['timestamp'])/1000000,
                'content': get_readable_content(event)
            })

        conversation['chatName'] = chatName(orig_conv, conversation['participants'])
        simpleJson.append(conversation)

def getName(user_id, conversation):
    global gaia_to_name
    # First use the locally defined one if available.
    for p in conversation['participants']:
        if user_id == p['id'] and p['name'] != None:
            return p['name']
    return gaia_to_name.get(user_id, user_id) # Fall back to global name, then to no name at all just ID.

def chatName(orig_conv, participants):
    if (('name' in orig_conv['conversation']['conversation']) and (orig_conv['conversation']['conversation']['name'] != "")):
        return orig_conv['conversation']['conversation']['name']
    for participant in participants:
        if participant['id'] == orig_conv['conversation']['conversation']['self_conversation_state']['self_read_state']['participant_id']['gaia_id']:
            return participant['name']

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('INPUT_JSON_PATH', help='Path location of Hangouts.json file obtained from Google Takeout.')
    parser.add_argument('OUTPUT_DIRECTORY', help='Path to write output files.')
    args = parser.parse_args()

    jsonData = json.load(open(args.INPUT_JSON_PATH, 'r'))
    simpleJson = []
    parseData()
    json.dump(simpleJson, open(os.path.join(args.OUTPUT_DIRECTORY, 'clean_hangoutsData.json'), 'w'), indent=4)
    for chat in simpleJson:
        filename = ', '.join(getName(i['id'],chat) for i in chat['participants'])+'.txt'
        if len(filename) > os.statvfs(args.OUTPUT_DIRECTORY).f_namemax:
            filename = hashlib.sha256(filename.encode('ascii')).hexdigest()+'.txt'
        with open(os.path.join(args.OUTPUT_DIRECTORY, filename), 'w') as outtext:
            for msg in chat['messages']:
                outtext.write(datetime.datetime.fromtimestamp(msg['unixtime']).strftime('%Y-%m-%d %H:%M:%S')+' '+msg['sender']['name']+': '+msg['content']+'\n')
